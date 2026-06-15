"""LLM-output -> structured wire response adapter (batch 2).

`extract_structured_response` is the single entrypoint that turns the
agent's final prose + tool-call returns into a `StructuredChatResponse`.
The function is pure (no I/O, no clock reads in the main path) so the
service layer can call it without a side-effecting context.

Dispatch is by `tool_name` (string) and uses `isinstance(content, X)` to
identify typed envelopes. Pydantic AI stores the raw Python object on
`ToolReturnPart.content` (per `BaseToolReturnPart.content: ToolReturnContent`
in pydantic-ai>=1.106), so the `isinstance` check is valid in-memory.
The JSON-roundtrip test in `test_service.py` notes that the same
`ToolReturnPart.content` becomes a `dict` after `ModelMessagesTypeAdapter`
reload — the typed-identity guarantee holds only in-memory.

References
----------
- `.opencode/plans/03-adapter.md` — the spec for this file.
- `.opencode/plans/15-backend-tests.md` — the golden tests in
  `tests/test_adapter.py`.
"""

from __future__ import annotations

import logging
import re
from typing import Final

from pydantic_ai.messages import ToolReturnPart

from advogado_de_bolso.contracts import DeadlineResult, DraftedDocument, KnowledgeChunk
from advogado_de_bolso.schemas import StructuredChatResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Question-extraction regexes (ISSUE-USR-010 fix)
# ---------------------------------------------------------------------------

_QUESTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # Pattern 1: numbered list items. MUST end in "?" (ISSUE-USR-010).
    # The previous `.+` matched any numbered list item, so non-questions like
    # "1. The customer should..." were mis-extracted as questions.
    re.compile(r"^\s*\d+\.\s+(.+\?)\s*$", re.MULTILINE),
    # Pattern 2: bullet items ending in "?".
    re.compile(r"^\s*[-*]\s+(.+?\?)", re.MULTILINE),
    # Pattern 3: keyword-led questions. The outer capture group wraps the
    # FULL question, and the keyword alternatives are non-capturing, so
    # `match.group(1)` returns "Posso cancelar a compra?" (not just "Posso").
    re.compile(
        r"\b((?:Posso|Poderia|Pode|Consegue|Você poderia)[^\n?]*\?)",
        re.IGNORECASE,
    ),
)


# ---------------------------------------------------------------------------
# Quick-reply chip sets
# ---------------------------------------------------------------------------

_DEFAULT_QUICK_REPLIES: Final[list[str]] = [
    "Explique melhor",
    "Cite a base legal",
    "Quero um modelo de documento",
]
_DEADLINE_QUICK_REPLIES: Final[list[str]] = [
    "Como interrompo o prazo?",
    "E se o defeito for oculto?",
    "Quero um modelo de notificação",
]
_DOC_QUICK_REPLIES: Final[list[str]] = [
    "Torne o tom mais firme",
    "Adicione a base legal (CDC)",
    "Encurte o texto",
]


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def extract_structured_response(
    prose: str,
    tool_returns: list[ToolReturnPart],
    *,
    blocked: bool = False,
    blocked_message: str | None = None,
) -> StructuredChatResponse:
    """Turn the agent's prose + tool-call returns into a wire response.

    Args:
        prose: The agent's final assistant message text.
        tool_returns: The `ToolReturnPart`s produced by the agent during the
            turn (in order). Each part's `content` is the raw Python object
            the tool returned (a `DeadlineResult`, `DraftedDocument`,
            `list[KnowledgeChunk]`, etc.) or a `str` (error path).
        blocked: If True, the response is a reviewer-blocked envelope and
            carries `blocked_message`.
        blocked_message: The reason the response was blocked, if any.

    Returns:
        A fully populated `StructuredChatResponse`. The service layer
        overwrites `session_id`, `updated_at`, and `chat_history` before
        returning to the API caller.
    """
    deadline: DeadlineResult | None = None
    template_letter: str | None = None
    relevant_chunks: list[KnowledgeChunk] = []

    for part in tool_returns:
        name = part.tool_name
        content = part.content  # raw Python object (NOT JSON string)

        if name == "calcular_prazo_consumidor" and isinstance(content, DeadlineResult):
            deadline = content
        elif name == "redigir_documento" and isinstance(content, DraftedDocument):
            template_letter = content.texto
        elif name == "search_knowledge_base":
            # `content` is a `list[KnowledgeChunk]` (or empty list, or a
            # tuple — accept any Sequence). Already typed by the tool; no
            # re-validation (see ISSUE-M3-011). Defensive copy via
            # `list(...)` so downstream code can safely iterate.
            if isinstance(content, (list, tuple)):
                relevant_chunks.extend(content)
        else:
            # Log unknown tool names to aid debugging new tools / typos
            # (ISSUE-DS-006). Fail-soft: do not raise.
            logger.warning("adapter: unknown tool return tool_name=%s", name)

    # Truncate relevant chunks to first 2 for relevant_title/relevant_content
    first_two = relevant_chunks[:2]
    relevant_title = first_two[0].fonte if first_two else ""
    relevant_content = "\n\n".join(c.texto for c in first_two)

    # step_title/step_content: first paragraph of prose, with fallback.
    # Filter out empty / whitespace-only paragraphs so the fallback
    # `"Análise inicial"` actually fires when prose is empty (ISSUE-004).
    paragraphs = [p for p in prose.strip().split("\n\n", 1) if p.strip()]
    if paragraphs:
        step_title = paragraphs[0].split("\n", 1)[0][:120]
        step_content = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
    else:
        step_title = "Análise inicial"
        step_content = ""

    # questions: numbered list or "Posso..." patterns in prose
    questions = _extract_questions(prose)

    # suggestive_text: last non-empty line of prose, truncated to 200
    suggestive_text = _extract_suggestive_text(prose)

    # quick_replies: contextual based on which tool was used
    quick_replies = _derive_quick_replies(deadline, template_letter)

    return StructuredChatResponse(
        session_id="",  # filled in by the service layer
        step_title=step_title,
        step_content=step_content,
        relevant_title=relevant_title,
        relevant_content=relevant_content,
        deadline=deadline,
        questions=questions,
        suggestive_text=suggestive_text,
        template_letter=template_letter,
        quick_replies=quick_replies,
        blocked=blocked,
        blocked_message=blocked_message,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_questions(prose: str) -> list[str]:
    """Extract the LLM's clarifying questions from the prose body.

    Strategy:
      1. Numbered list items (`1. ...?`).
      2. Bullet items ending in `?`.
      3. Sentences starting with Posso/Poderia/Pode/Consegue/Você poderia + `?`.
    De-duplicates while preserving order. Caps at 5 questions.
    """
    if not prose:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for pattern in _QUESTION_PATTERNS:
        for match in pattern.finditer(prose):
            candidate = match.group(1).strip() if match.lastindex else match.group(0).strip()
            candidate = candidate.rstrip("?. ").rstrip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                out.append(candidate + "?")
            if len(out) >= 5:
                return out
    return out


def _extract_suggestive_text(prose: str) -> str | None:
    """Return the last non-empty line of the prose, truncated to 200 chars.

    The "suggestive" UI line is shown after the main analysis. We use the
    last non-empty line of the prose, trimmed to 200 chars, as a heuristic.
    """
    if not prose or not prose.strip():
        return None
    lines = [ln.strip() for ln in prose.strip().splitlines() if ln.strip()]
    if not lines:
        return None
    last = lines[-1]
    return last[:200] if last else None


def _derive_quick_replies(
    deadline: DeadlineResult | None,
    template_letter: str | None,
) -> list[str]:
    """Return a context-appropriate list of 3 quick-reply chips.

    - If a `redigir_documento` letter was produced, suggest follow-ups
      about tone, legal basis, and length.
    - Else if a `calcular_prazo_consumidor` deadline was produced, suggest
      follow-ups about interrupting the deadline, hidden defects, and
      drafting a notification.
    - Otherwise, fall back to generic exploration chips.
    """
    if template_letter:
        return list(_DOC_QUICK_REPLIES)
    if deadline is not None:
        return list(_DEADLINE_QUICK_REPLIES)
    return list(_DEFAULT_QUICK_REPLIES)


__all__ = [
    "extract_structured_response",
    "_extract_questions",
    "_extract_suggestive_text",
    "_derive_quick_replies",
    "_DEFAULT_QUICK_REPLIES",
    "_DEADLINE_QUICK_REPLIES",
    "_DOC_QUICK_REPLIES",
    "_QUESTION_PATTERNS",
]
