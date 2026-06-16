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
# Title detection (long-form responses only)
# ---------------------------------------------------------------------------

_TITLE_MAX_CHARS: int = 200
_RAG_SNIPPET_MAX_CHARS: int = 400


def _is_title_line(line: str) -> bool:
    """Heuristic: a first line is treated as a title iff it is short,
    fully wrapped in `**...**` (a single bold span, no nested bold), and
    the agent used bold deliberately to mark it as a title.

    The LLM is instructed (see `agent.SYSTEM_PROMPT`) to begin long
    formal responses (document drafts, multi-article analyses) with such
    a line. Conversational responses do not use this pattern, so the
    first line is treated as ordinary content — `step_title` stays empty
    and the whole prose lands in `step_content`. This keeps normal chat
    turns from being rendered as "posts with titles".
    """
    line = line.strip()
    if not line or len(line) > _TITLE_MAX_CHARS:
        return False
    if not (line.startswith("**") and line.endswith("**")):
        return False
    # The interior must be a single bold span (no nested `**`).
    return "**" not in line[2:-2]


def _truncate_snippet(text: str, max_chars: int = _RAG_SNIPPET_MAX_CHARS) -> str:
    """Truncate `text` at the previous word boundary within `max_chars`,
    appending `...` if truncated. The full chunk text is preserved in
    `case.model_history`; this helper only shapes the wire response so
    the UI does not render a wall of legal prose under every reply.
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "..."


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
    template_letter_assunto: str | None = None
    relevant_chunks: list[KnowledgeChunk] = []

    for part in tool_returns:
        name = part.tool_name
        content = part.content  # raw Python object (NOT JSON string)

        if name == "calcular_prazo_consumidor" and isinstance(content, DeadlineResult):
            deadline = content
        elif name == "redigir_documento" and isinstance(content, DraftedDocument):
            template_letter = content.texto
            template_letter_assunto = content.assunto or None
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

    # Truncate relevant chunks to first 2 for relevant_title/relevant_content.
    # Each chunk's `texto` is capped at `_RAG_SNIPPET_MAX_CHARS` so the wire
    # response carries a snippet, not a wall of legal prose.
    first_two = relevant_chunks[:2]
    relevant_title = first_two[0].fonte if first_two else ""
    relevant_content = "\n\n".join(_truncate_snippet(c.texto) for c in first_two)

    # step_title / step_content split. The agent's SYSTEM_PROMPT tells the
    # LLM to begin long formal responses with a short bold title
    # (`**...**`); conversational responses stay unformatted. The adapter
    # detects the title via `_is_title_line` and only then splits it out.
    # Conversational turns land entirely in `step_content` with
    # `step_title == ""` so the UI renders a normal chat message.
    paragraphs = [p for p in prose.strip().split("\n\n", 1) if p.strip()]
    if not paragraphs:
        step_title = "Análise inicial"
        step_content = ""
    else:
        first_para = paragraphs[0]
        first_line = first_para.split("\n", 1)[0]
        if _is_title_line(first_line):
            step_title = first_line.strip().strip("*").strip()
            # Content = everything after the title line in the first
            # paragraph, plus the second paragraph (if any).
            tail = first_para[len(first_line):].lstrip("\n")
            second = paragraphs[1] if len(paragraphs) > 1 else ""
            step_content = (
                tail + "\n\n" + second if tail and second else tail or second
            )
        else:
            # No title — the whole prose is content. Leave `step_title`
            # empty so the UI does not render a header on a normal
            # conversational turn.
            step_title = ""
            step_content = prose

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
        template_letter_assunto=template_letter_assunto,
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
    "_is_title_line",
    "_truncate_snippet",
    "_DEFAULT_QUICK_REPLIES",
    "_DEADLINE_QUICK_REPLIES",
    "_DOC_QUICK_REPLIES",
    "_QUESTION_PATTERNS",
]
