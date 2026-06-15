# Integration Plan (Revised v2): base_frontend React UI → Python FastAPI Backend

> **Replaces** `.opencode/plans/revised-integration-plan.md` — incorporates all consensus fixes from the 3-reviewer loop.

---

## Architecture Summary

- **Single FastAPI server** on port 8000 serves the API and (in prod) the React build.
- **Dev**: Vite standalone on port 5173 with `server.proxy` forwarding `/api/*` → FastAPI.
- **Prod**: `base_frontend/dist/` served via an explicit SPA fallback route (NOT `StaticFiles(html=True)`) on FastAPI. `/api/*` routes take precedence.
- **Adapter pipeline**: Tools return typed Pydantic `BaseModel` envelopes for success, plain strings for error paths. The adapter reads `ToolReturnPart.content` directly. Pydantic AI stores the raw Python return on `BaseToolReturnPart.content` (typed as `ToolReturnContent`, an alias union in Pydantic AI 1.106+; the `Any` top-level permits typed objects). The `tool_plain` round-trip is NOT guaranteed to preserve raw objects through every model provider (e.g., Google Gemini may stringify) — the implementer MUST add a contract test in `tests/test_adapter.py` that mocks a `ToolReturnPart` with a `DeadlineResult` and asserts `isinstance(part.content, DeadlineResult)`. See ISSUE-006. Dispatch is by `tool_name` (not by type-tries), because `tool_kind` is `None` for user-defined tools (per the `ToolPartKind | None = None` annotation on `BaseToolReturnPart.tool_kind`).
- **Case persistence**: One JSON file per case at `./storage/cases/{case_id}.json`. Disk is the source of truth. `case_id == session_id == one UUID`. No `_index.json` — `list_all()` scans the directory directly (acceptable for <1000 cases). Per-case `asyncio.Lock` with cleanup on delete.
- **`response_style` injection**: Pydantic AI's `@agent.instructions` decorator registers a callback that reads from a `ContextVar` set per `chat_structured` call. The agent is built **once** at startup; no per-request rebuild. `Deps` stays clean (no `response_style` field).
- **Error envelope**: Reviewer-blocked responses return HTTP `422 Unprocessable Entity` with `{"blocked": true, "blocked_message": "..."}`. Frontend handles via the existing `!response.ok` branch.
- **Auto-create UX**: First chat message with `session_id: null` creates a case server-side. The frontend sends `title` and `icon_name` derived from the first user message in the request body. `handleSaveCaseFromChat` becomes a metadata update (`PATCH /api/cases/{case_id}` with `UpdateCaseRequest { title?, icon_name?, response_style? }`) that refreshes title/icon (ISSUE-USR-005).
- **Demo cases**: Three seed cases ship in `defaults.ts` marked `is_demo: true`. The frontend renders them with a "DEMO" badge and clears them when the first real case is created.
- **CLI**: Stays on `agent.run_stream` + writes case files via the storage layer directly. Does not go through `ChatService`. Streaming UX preserved.
- **No Express, no Gemini direct calls.** `server.ts` deleted.

---

## Files to Create

### `src/advogado_de_bolso/contracts.py`
Typed tool return envelopes (Pydantic BaseModel). Successes return these; errors return plain strings.

```python
from __future__ import annotations
from datetime import date
from typing import Literal

from pydantic import BaseModel

TipoPrazo = Literal["reclamacao_vicio", "arrependimento"]
Tom = Literal["formal", "cordial", "firme"]


class DeadlineResult(BaseModel):
    tipo_prazo: TipoPrazo
    data_inicio: date
    data_limite: date
    dias: int
    base_legal: str          # "CDC art. 49"
    item_label: str | None
    vicio_oculto: bool
    nota: str


class DraftedDocument(BaseModel):
    tipo: str                # echoes the tool's `tipo` argument
    tom: Tom                 # echoes the tool's `tom` argument
    destinatario: str        # echoes the tool's `destinatario` argument
    texto: str               # the actual drafted prose (from the sub-LLM)


class KnowledgeChunk(BaseModel):
    fonte: str               # never None; "fonte desconhecida" is the fallback
    texto: str
```

Notes:
- `calculos.py` keeps the existing `str` return for its **error paths** (missing `tipo_item`, invalid date, invalid `tipo_prazo`). Only successful calculations return `DeadlineResult`. This means the adapter uses `isinstance(part.content, DeadlineResult)` and gracefully ignores string returns (which represent the LLM asking the user for clarification).
- `DraftedDocument` keeps the full envelope (per Open Issue #8 = A). The redundant `tipo`/`tom`/`destinatario` echoes keep the adapter self-describing; mild LLM-context noise is accepted.
- `KnowledgeChunk.fonte` must preserve the "fonte desconhecida" fallback from `tools/rag.py:39`.

### `src/advogado_de_bolso/schemas.py`
Wire types for the API. All fields snake_case.

- `StructuredChatRequest { message, session_id: UUID | None, response_style?, title?, icon_name? }`
  - `session_id` MUST be a `UUID`-typed field (Pydantic auto-validates and rejects malformed values with a 422). The server never accepts an arbitrary string for `session_id` (ISSUE-USR-001). The first-message auto-create case (`session_id=None`) generates a fresh `uuid.uuid4()` server-side.
  - `title` and `icon_name` are sent on the **first** message of a new case (when `session_id` is null). Server uses them to populate the case file. Subsequent messages ignore them.
  - `response_style` is per-request; the `_current_style` ContextVar overrides the persisted case default for the current turn only. The case default is set on first creation and read back on subsequent turns when the request does not include a `response_style` (ISSUE-M3-007 + ISSUE-DS-009).
- `StructuredChatResponse { session_id, step_title, step_content, relevant_title, relevant_content, deadline, questions, suggestive_text, template_letter, quick_replies, blocked, blocked_message }`
- `CaseSummary { id, title, created_at, updated_at, last_message, icon_name, response_style, tag_text?, is_demo }`
  - `last_message` is the last assistant message's `step_content` (or `text`), truncated to 80 chars.
  - `is_demo: bool` is true for the three seed cases. Frontend renders a "DEMO" badge for these.
- `CaseResponse { id, title, chat_history: list[ChatMessage] }`
- `ChatMessage` — Python mirror of the React `ChatMessage` in snake_case. `timestamp: int` (milliseconds since epoch — explicit, to avoid Pydantic auto-coercing to ISO string). All other fields are `Optional`.
- `RenameCaseRequest { title }` — DEPRECATED. Replaced by `UpdateCaseRequest` (see below). Retained here only for historical reference; PATCH now uses `UpdateCaseRequest`.
- `UpdateCaseRequest { title?, icon_name?, response_style? }` — the PATCH body for `PATCH /api/cases/{case_id}`. All fields are optional; at least one MUST be set (Pydantic `model_validator` enforces this with a 422 if none are provided). The `response_style` field accepts the same `Literal["simples", "detalhado", "firme"]` values as `StructuredChatRequest.response_style`. ISSUES-M3-008 + USR-005: the previous `RenameCaseRequest { title }` body could not carry `icon_name` or `response_style`, but the frontend needs to PATCH all three.

### `src/advogado_de_bolso/adapter.py`
Pure transformation function. Dispatch by `tool_name` to avoid type-tries on user tools (`tool_kind = None`).

```python
def extract_structured_response(
    prose: str,
    tool_returns: list[ToolReturnPart],
    *,
    blocked: bool = False,
    blocked_message: str | None = None,
) -> StructuredChatResponse:
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
            # content is a list[KnowledgeChunk] (or empty list, or a tuple —
            # accept any Sequence). Already typed by the tool; no re-validation
            # (see ISSUE-M3-011). Defensive copy via list() so downstream code
            # can safely iterate.
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

    # suggestive_text: sentence after the analysis
    suggestive_text = _extract_suggestive_text(prose)

    # quick_replies: contextual based on which tool was used
    quick_replies = _derive_quick_replies(deadline, template_letter)

    return StructuredChatResponse(
        session_id="",  # filled in by chat_structured
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
```

Critical: `isinstance(content, DeadlineResult)` — NOT `model_validate_json(content)`. Pydantic AI stores raw objects in `ToolReturnPart.content` (per the `ToolReturnContent` type alias on `BaseToolReturnPart.content`); `model_validate_json` would throw because the content is the raw Python object, not a JSON string. The `tool_plain` round-trip caveat from ISSUE-006 still applies.

#### Adapter helper functions (ISSUE-003)

The three helpers referenced by `extract_structured_response` are spec'd below. All are pure functions of `prose` (or of the extracted tool results), with deterministic regex-based extraction and safe fallbacks.

```python
import logging
import re
from typing import Final

logger = logging.getLogger(__name__)

_QUESTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # ISSUE-USR-010: pattern 1 now requires the numbered item to END in "?".
    # The previous `.+` matched any numbered list item, so non-questions like
    # "1. The customer should..." were mis-extracted as questions.
    re.compile(r"^\s*\d+\.\s+(.+\?)\s*$", re.MULTILINE),          # "1. ...?"
    re.compile(r"^\s*[-*]\s+(.+?\?)", re.MULTILINE),            # "- ...?"
    # ISSUE-USR-010: pattern 3 has a SINGLE capture group wrapping the
    # full question (keyword + body + "?"), so `match.group(1)` returns
    # the entire "Posso cancelar a compra?" instead of just "Posso".
    re.compile(r"\b(Posso|Poderia|Pode|Consegue|Você poderia)[^\n?]*\?", re.IGNORECASE),
)
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


def _extract_questions(prose: str) -> list[str]:
    """Extract the LLM's clarifying questions from the prose body.

    Strategy:
      1. Find numbered list items (`1. ...`).
      2. Find bullet items ending in `?`.
      3. Find sentences starting with Posso/Poderia/Pode/Consegue/Você poderia + `?`.
    De-duplicate while preserving order. Cap at 5 questions.
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
    """Return the last sentence of the prose, or None if the prose is empty.

    The 'suggestive' UI line is meant to be a short follow-up cue shown after
    the main analysis. We use the last non-empty line of the prose, trimmed
    to 200 chars, as a heuristic.
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

    - If a `redigir_documento` letter was produced, suggest follow-ups about
      tone, legal basis, and length.
    - Else if a `calcular_prazo_consumidor` deadline was produced, suggest
      follow-ups about interrupting the deadline, hidden defects, and drafting
      a notification.
    - Otherwise, fall back to generic exploration chips.
    """
    if template_letter:
        return list(_DOC_QUICK_REPLIES)
    if deadline is not None:
        return list(_DEADLINE_QUICK_REPLIES)
    return list(_DEFAULT_QUICK_REPLIES)
```

### `src/advogado_de_bolso/storage/__init__.py`
Empty package init.

### `src/advogado_de_bolso/storage/cases.py`
Per-case JSON persistence. **No `_index.json`**: `list_all()` scans the directory directly.

- `Case` model: `id, title, created_at, updated_at, response_style, icon_name, is_demo, chat_history: list[ChatMessage], model_history: list[ModelMessage]`
  - `model_history` is the LLM-bound history (raw `ModelMessage` objects appended from `result.new_messages()` on each turn) and is **required** for multi-turn quality (ISSUE-M3-001 + ISSUE-USR-002). It preserves `ToolCallPart`/`ToolReturnPart` payloads across turns. The wire `chat_history` is for the UI; `model_history` is for the LLM. Critically, persistence uses `result.new_messages()` (current turn only) — not `result.all_messages()` — so prior turns' tool returns are not double-counted.
- Functions: `load(case_id, *, cases_path: Path)`, `save(case, *, cases_path: Path)`, `delete(case_id, *, cases_path: Path)`, `list_all(*, cases_path: Path) -> list[CaseSummary]`. **All four functions take a `cases_path: Path` keyword-only argument** (ISSUE-USR-007); the `ChatService` passes `self._cases_path` (which it received from `Settings.cases_path`) on every call. The functions MUST NOT hardcode `./storage/cases` — doing so would defeat the `CASES_PATH` env var.
- File layout: `./storage/cases/{case_id}.json` (configurable via `Settings.cases_path` with env alias `CASES_PATH` — see ISSUE-M3-014 + ISSUE-USR-007)
- **Path containment** (ISSUE-USR-001): every storage function (`load`, `save`, `delete`) takes a `case_id` and constructs `cases_path / f"{case_id}.json"`. After construction, the resolved absolute path MUST satisfy `file_path.resolve().is_relative_to(cases_path.resolve())`; otherwise the function raises `ValueError`. Combined with the `UUID` typing of `StructuredChatRequest.session_id` (see `schemas.py`), this prevents path-traversal inputs like `../../etc/passwd` from escaping `cases_path`. The `case_id` value MUST be either a freshly-generated `uuid.uuid4()` (server-side) or a Pydantic-validated `UUID` (client-supplied).
- **Directory creation**: `save()` calls `file_path.parent.mkdir(parents=True, exist_ok=True)` before writing. The `cases_path` is also created at `ChatService.__init__` time so the first save is a no-op directory-wise. See ISSUE-005.
- Atomic writes: write to `{case_id}.json.tmp` then `os.replace()` (per Open Issue #U; `Path.replace` and `os.replace` are the same on Python 3, but be explicit).
- Per-case `asyncio.Lock` with cleanup on delete (per Open Issue #10 = A). The lock registry uses a single meta-lock to protect the dict itself.
- `list_all()` reads each `{case_id}.json` and returns a `CaseSummary` for each. For <1000 cases this is fast enough; no index file is needed.
- **Scalability constraint** (ISSUE-DS-007): the `list_all()` docstring MUST document that this implementation is acceptable only for `<1000` case files. Each call performs one `json.loads` per file plus one `os.listdir`. Above 1000 cases, latency degrades linearly. A soft warning is logged at `INFO` level when the file count exceeds 500. See Out-of-Scope Notes for the upgrade path.

### `src/advogado_de_bolso/agent.py`
Builds the agent **once**. Uses `@agent.instructions` to compose the system prompt dynamically.

```python
STYLE_PROMPTS: dict[str, str] = {
    "simples": (
        "\n\nESTILO DE RESPOSTA: simples\n"
        "- Linguagem acessível, sem jargões.\n"
        "- Frases curtas e diretas.\n"
        "- Não citar artigos do CDC a menos que o usuário peça."
    ),
    "detalhado": (
        "\n\nESTILO DE RESPOSTA: detalhado (padrão)\n"
        "- Análise completa com artigos do CDC citados.\n"
        "- Explicar nuances e ressalvas."
    ),
    "firme": (
        "\n\nESTILO DE RESPOSTA: firme\n"
        "- Tom assertivo, formal.\n"
        "- Citar artigos do CDC e consequências legais.\n"
        "- Adequado para uso em notificações extrajudiciais."
    ),
}

_current_style: ContextVar[str | None] = ContextVar("_current_style", default=None)


def build_agent(settings: Settings) -> Agent[Deps, str]:
    if resolved_key := settings.resolved_google_api_key:
        os.environ["GOOGLE_API_KEY"] = resolved_key

    model = settings.full_model_name

    agent = Agent(
        model=model,
        deps_type=Deps,
        system_prompt=SYSTEM_PROMPT,  # updated below
        model_settings=settings.build_model_settings(),
    )

    @agent.instructions
    def _style_instructions() -> str | None:
        style = _current_style.get()
        return STYLE_PROMPTS.get(style) if style else None

    agent.tool(search_knowledge_base)
    agent.tool_plain(calcular_prazo_consumidor)
    agent.tool(redigir_documento)
    return agent
```

`SYSTEM_PROMPT` is **updated** in full. The previous excerpts at lines 320-323 of the prior plan revision are replaced with the complete merged prompt below (ISSUE-011):

```python
SYSTEM_PROMPT: str = """Você é o **Advogado de Bolso**, um assistente jurídico informal
para consumidores brasileiros. Você ajuda pessoas a entender seus direitos
previstos no Código de Defesa do Consumidor (Lei 8.078/90) e a redigir
documentos simples (e-mails de cobrança, reclamações, notificações).

## Princípios inegociáveis
1. Responda **sempre em português brasileiro** em tom cordial e acessível.
2. **Nunca invente** números de artigos, de processos, de leis esparsas ou
   de datas. Quando não souber, diga que não sabe e recomende consultar
   um advogado.
3. Para casos complexos (ações judiciais, valores altos, contratos
   sofisticados), recomende expressamente a consulta a um advogado
   inscrito na OAB.
4. Toda resposta sua passa por um revisor automático antes de ser
   entregue ao usuário. Respostas com erros factuais ou jurídicos
   graves são bloqueadas.

## Ferramentas disponíveis
Você tem três ferramentas à disposição. Use-as quando o problema do
usuário realmente exigir.

### `calcular_prazo_consumidor`
Calcula prazos do CDC. Retorna um objeto JSON com os campos
`tipo_prazo`, `data_inicio`, `data_limite`, `dias`, `base_legal`,
`item_label`, `vicio_oculto`, `nota`.
Use esses campos para escrever uma resposta clara que inclua **a data
limite** e **a base legal**. Se a ferramenta retornar uma string em
português (caminho de erro), retransmita o erro ao usuário e peça a
informação faltante.

### `redigir_documento`
Redige um documento. Retorna um objeto JSON com `tipo`, `tom`,
`destinatario` e `texto`. Apresente **apenas o campo `texto`** ao
usuário como o corpo do documento. Não parafraseie, não resuma, não
adicione comentários antes ou depois do texto.

### `search_knowledge_base`
Busca trechos relevantes na base de conhecimento do CDC. Retorna uma
lista de objetos `{fonte, texto}`. Se a lista contiver um único item com
`fonte="sistema"` e `texto="Nenhum trecho relevante foi encontrado na
base de conhecimento."`, isso significa que **nada relevante foi
encontrado** — NÃO cite `sistema` como fonte; apenas diga ao usuário
que a base não tem cobertura suficiente para o caso dele e, se
aplicável, recomende a consulta a um advogado. Se a lista contiver
trechos reais (com `fonte` diferente de `"sistema"`), cite a `fonte`
na sua resposta.

## Estilo
- Frases curtas. Listas numeradas ou com marcadores quando ajudar.
- Use **negrito** para destacar prazos, valores e artigos do CDC.
- Evite jargão desnecessário; quando usar, explique em uma frase.
"""
```

### `src/advogado_de_bolso/service.py`
Major rewrite. `ChatService.chat_structured` is the new primary method. No `_max_sessions` (disk is the source of truth). No `_max_history_messages` cap on persistence, but a **20-turn cap on the LLM-bound slice** (per Open Issue #9 = A).

```python
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import suppress
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
# ISSUE-USR-001: `UUID` is used to type `chat_structured(session_id)`
# so the service signature matches the Pydantic-validated
# `StructuredChatRequest.session_id: UUID | None`. Pydantic rejects
# malformed UUIDs with 422 at the API layer.
from uuid import UUID

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
    TextPart,
)
from pydantic_ai.tools import AgentRunResult

from . import schemas
from .contracts import DeadlineResult
from .schemas import (
    CaseSummary,
    ChatMessage,
    StructuredChatResponse,
)
# ISSUE-USR-006: `Case` is the persistent storage model defined in
# `storage/cases.py` (see plan line 259), NOT in `schemas.py` (which only
# defines the wire types `CaseResponse`, `CaseSummary`, `ChatMessage`,
# `UpdateCaseRequest`, `StructuredChatRequest`, `StructuredChatResponse`).
# The previous import `from .schemas import Case` would raise
# `ImportError: cannot import name 'Case' from 'advogado_de_bolso.schemas'`
# at import time. Import from the storage module instead.
from .storage.cases import Case
from .storage import cases
from .adapter import extract_structured_response
from .tools.revisor import RevisionResult

logger = logging.getLogger(__name__)

# ISSUE-IND-001: `REVIEW_BLOCKED_MESSAGE` is defined locally in `service.py`
# rather than imported from `.tools.revisor`. The constant is tightly coupled
# to the service layer's reviewer-blocking behavior and has no reason to live
# in `tools.revisor` (which only exports `RevisionResult` and the
# `review_response` callable). Importing it from `tools.revisor` would raise
# `ImportError: cannot import name 'REVIEW_BLOCKED_MESSAGE' from
# 'advogado_de_bolso.tools.revisor'` at import time. The text matches the
# reviewer-blocked UX message already in use at `service.py:21-25`.
REVIEW_BLOCKED_MESSAGE = (
    "Nao foi possivel validar esta resposta com seguranca. "
    "Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica "
    "ou um advogado de confianca."
)

# ISSUE-DS-001: `_now()` is defined at module scope (was previously referenced
# without a definition — would have caused NameError on first chat).
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_ms() -> int:
    """Integer milliseconds since the Unix epoch. Uses `time.time_ns()` to
    avoid the float-multiplication `int(time.time() * 1000)` pattern that mypy
    strict flags."""
    return time.time_ns() // 1_000_000


@dataclass(frozen=True)
class ChatResult:
    """Wire-result wrapper for `chat_structured`.

    Renamed from `StructuredChatResponse` to avoid the self-naming collision
    with `schemas.StructuredChatResponse` (ISSUE-002). A field typed
    `response: StructuredChatResponse` inside a class also named
    `StructuredChatResponse` would resolve to the class being defined, not
    the schemas type — confusing to mypy and to readers.
    """
    session_id: str
    response: "schemas.StructuredChatResponse"  # always string-quoted import path


class ChatBackend(Protocol):
    """Plain `run(message, history) -> (prose, new_messages)` contract.

    The backend does NOT run the reviewer. The reviewer is called by
    `ChatService` (ISSUE-M3-003). The returned `prose` is the raw agent
    output; the returned `new_messages` is the **current turn's** `ModelMessage`
    list from `result.new_messages()` (excluding the input `message_history`
    and any prior runs). This is the only set of messages the adapter should
    inspect for tool returns — prior-turn returns live in `case.model_history`
    and are NOT re-examined (ISSUE-USR-002).
    """
    async def run(
        self,
        message: str,
        history: list[ModelMessage],
    ) -> tuple[str, list[ModelMessage]]: ...


class ReviewerLike(Protocol):
    async def __call__(self, question: str, response: str) -> RevisionResult: ...


class ChatService:
    def __init__(
        self,
        backend: ChatBackend,
        reviewer: ReviewerLike,
        *,
        cases_path: Path,
        max_llm_history_turns: int = 20,
    ) -> None:
        if max_llm_history_turns < 1:
            raise ValueError("max_llm_history_turns must be positive.")
        self._backend = backend
        self._reviewer = reviewer
        # ISSUE-USR-007: `cases_path` is injected from `Settings.cases_path`
        # (with env alias `CASES_PATH`) so the env var actually controls
        # persistence. Previously the path was hardcoded to
        # `Path("./storage/cases")` and the `Settings.cases_path` field was
        # dead. The storage layer receives the same path through
        # `self._cases.save(case, cases_path=self._cases_path)` etc.
        self._cases_path = cases_path
        self._max_llm_history_turns = max_llm_history_turns
        self._case_locks: dict[str, asyncio.Lock] = {}
        self._locks_meta_lock = asyncio.Lock()
        # Ensure the cases directory exists at startup (ISSUE-005).
        # We use `self._cases_path` (not a hardcoded path) so the
        # `CASES_PATH` env var is honored.
        with suppress(Exception):
            self._cases_path.mkdir(parents=True, exist_ok=True)

    async def _get_case_lock(self, case_id: str) -> asyncio.Lock:
        async with self._locks_meta_lock:
            lock = self._case_locks.get(case_id)
            if lock is None:
                lock = asyncio.Lock()
                self._case_locks[case_id] = lock
            return lock

    async def _release_case_lock(self, case_id: str) -> None:
        """Release the per-case lock.

        ISSUE-M3-006 (lock-cleanup race): we only pop the lock from the
        registry AFTER the file delete succeeds, and `delete_case` itself
        acquires the per-case lock before deleting, so a concurrent
        `chat_structured` either runs strictly before the delete or strictly
        after. The window where the lock could leak is reduced to a
        never-observed single-task race. The in-flight `chat_structured`
        keeps its reference to the OLD lock via the local `lock` variable
        and is not affected by registry eviction.
        """
        async with self._locks_meta_lock:
            self._case_locks.pop(case_id, None)

    async def chat_structured(
        self,
        message: str,
        session_id: UUID | None = None,
        *,
        response_style: Literal["simples", "detalhado", "firme"] | None = None,
        title: str | None = None,
        icon_name: str | None = None,
    ) -> ChatResult:
        # ISSUE-USR-001: `session_id` is `UUID | None`. Pydantic has already
        # validated it (UUID-typed `StructuredChatRequest.session_id` rejects
        # malformed values with a 422 at the API layer). `str(uuid_obj)` is
        # always a safe filename fragment (only `[0-9a-f-]`).
        case_id = str(session_id) if session_id is not None else str(uuid.uuid4())
        lock = await self._get_case_lock(case_id)
        async with lock:
            # Load (or create) the case. Track whether this turn created a
            # brand-new case — used by ISSUE-USR-004 to avoid persisting
            # an orphan file when the reviewer blocks the first message.
            case = cases.load(case_id, cases_path=self._cases_path)
            was_new_case = case is None
            if case is None:
                case = Case(
                    id=case_id,
                    title=title or "Nova consulta",
                    icon_name=icon_name or "gavel",
                    # ISSUE-M3-007: response_style is persisted as the
                    # case default on first creation. It is also injected
                    # per-request via the `_current_style` ContextVar,
                    # which OVERRIDES the persisted default for the
                    # current turn only. Subsequent turns use the
                    # persisted default unless an explicit style is sent.
                    response_style=response_style or "detalhado",
                    is_demo=False,
                    created_at=_now(),
                    updated_at=_now(),
                    chat_history=[],
                    # ISSUE-M3-001: persist the LLM-bound history
                    # separately from the wire chat_history so that
                    # `ToolCallPart`/`ToolReturnPart` payloads survive
                    # across turns.
                    model_history=[],
                )
            elif title or icon_name:
                # First-message update of metadata
                if title:
                    case.title = title
                if icon_name:
                    case.icon_name = icon_name

            # ISSUE-DS-009: set the `_current_style` ContextVar AFTER the
            # case is loaded so that on subsequent turns (where
            # `response_style` is None) the persisted `case.response_style`
            # is used as the fallback. The fallback chain is:
            #   request response_style  >  case.response_style  >  "detalhado"
            # The ContextVar is reset at the end of the request via a
            # nested `try/finally` (replacing the previous outer
            # `try/finally` that set the ContextVar before the lock).
            effective_style = response_style or case.response_style or "detalhado"
            style_token: Token[str | None] = _current_style.set(effective_style)
            try:
                # Cap the LLM-bound history to the last N TURNS — not raw
                # ModelMessage count (ISSUE-USR-003). A single user turn that
                # uses tools emits 2-4 ModelMessages (ModelRequest →
                # ModelResponse with ToolCallPart → ModelRequest with
                # ToolReturnPart). Slicing by raw message count can orphan
                # a ToolReturnPart from its matching ToolCallPart, producing
                # invalid provider history (Anthropic/Gemini reject with
                # 400). We group messages into turns at the user-prompt
                # boundary (a `ModelRequest(parts=[UserPromptPart, ...])`
                # starts a new turn) and slice to the last N complete
                # turn groups, so every tool call/return pair stays paired.
                llm_history = _truncate_history_to_turns(
                    case.model_history, self._max_llm_history_turns
                )

                # Run the agent (returns raw prose + the current turn's
                # new ModelMessage history — see ISSUE-USR-002).
                prose, new_messages = await self._backend.run(
                    message, llm_history
                )

                # Run the reviewer (ISSUE-M3-003: the backend does NOT run
                # the reviewer; the service does, exactly once per turn).
                revision = await self._reviewer(message, prose)
                blocked = not revision.approved_as_is
                blocked_message = REVIEW_BLOCKED_MESSAGE if blocked else None
                if blocked:
                    prose = blocked_message or ""

                # Extract structured data — inspect ONLY the current turn's
                # tool returns (new_messages). Prior turns' returns live in
                # case.model_history and are NOT re-examined (ISSUE-USR-002).
                tool_returns = _collect_tool_returns(new_messages)
                structured = extract_structured_response(
                    prose, tool_returns,
                    blocked=blocked, blocked_message=blocked_message,
                )
                structured.session_id = case_id

                # Append user + assistant messages to chat_history.
                # ISSUE-008: use two distinct timestamps so the user
                # message and the assistant message cannot collide on
                # the millisecond suffix of their IDs.
                user_ts = _now_ms()
                assistant_ts = user_ts + 1
                case.chat_history.append(ChatMessage(
                    id=f"user-{user_ts}",
                    sender="user",
                    text=message,
                    timestamp=user_ts,
                ))
                case.chat_history.append(ChatMessage(
                    id=f"assistant-{assistant_ts}",
                    sender="assistant",
                    text=prose,
                    timestamp=assistant_ts,
                    step_title=structured.step_title,
                    step_content=structured.step_content,
                    relevant_title=structured.relevant_title,
                    relevant_content=structured.relevant_content,
                    deadline=structured.deadline.model_dump(mode="json") if structured.deadline else None,
                    questions=structured.questions,
                    suggestive_text=structured.suggestive_text,
                    template_letter=structured.template_letter,
                    quick_replies=structured.quick_replies,
                ))
                case.updated_at = _now()
                # Persist the new turn's ModelMessage appended to the prior
                # model_history so the next turn has full tool-call/return
                # context (ISSUE-M3-001). We use new_messages (current turn
                # only) — NOT all_messages — so we don't double-persist prior
                # turns' messages (ISSUE-USR-002).
                case.model_history = case.model_history + new_messages

                # ISSUE-USR-004: do NOT persist a brand-new case that the
                # reviewer blocked. The previous plan saved the case
                # unconditionally, which orphaned `{case_id}.json` files on
                # disk when the frontend's `!response.ok` branch surfaced
                # only the `blocked_message` and did not capture the
                # `session_id` for retry. Now: if the reviewer blocked AND
                # the case was just created in this call (`was_new_case`),
                # skip `cases.save(case)` and return the 422 envelope with
                # `session_id` populated so the frontend can retry against
                # the same case ID (no orphaned file on disk). The 422
                # response body still includes the assistant message and
                # `blocked_message` for the user to read.
                if blocked and was_new_case:
                    logger.info(
                        "chat_structured: reviewer blocked new case case_id=%s; "
                        "skipping save to avoid orphan",
                        case_id,
                    )
                else:
                    # ISSUE-M3-015: error contract — `cases.save` is called
                    # BEFORE the response is built. If save fails, an exception
                    # propagates to the API layer (which converts to 503).
                    # We do not silently swallow backend or save errors here.
                    # ISSUE-USR-007: pass `cases_path=self._cases_path` so the
                    # `CASES_PATH` env var actually controls the persistence
                    # location.
                    cases.save(case, cases_path=self._cases_path)

                return ChatResult(session_id=case_id, response=structured)
            finally:
                _current_style.reset(style_token)

    async def list_cases(self) -> list[CaseSummary]:
        # ISSUE-USR-007: thread the configured cases_path through to the
        # storage layer.
        return cases.list_all(cases_path=self._cases_path)

    async def get_case(self, case_id: str) -> Case | None:
        # ISSUE-USR-007: thread cases_path through to `cases.load`.
        return cases.load(case_id, cases_path=self._cases_path)

    # ISSUE-IND-002: a dedicated `rename_case` method was removed. The old
    # `PATCH /api/cases/{case_id}` wiring (USR-005) already delegates to
    # `update_case_meta`, so a single-field rename is just
    # `update_case_meta(case_id, title=new_title)`. The frontend
    # `apiClient.renameCase` is collapsed into a thin PATCH wrapper around
    # `updateCaseMeta({ title: newTitle })` (see `base_frontend/src/api.ts`
    # spec and `handleRenameCase` in `App.tsx`). Keeping a separate
    # `rename_case` would be dead code on the server side and a divergence
    # between the two call paths the frontend could take.

    async def update_case_meta(
        self, case_id: str, **fields: Any
    ) -> Case:
        """ISSUE-M3-008: wire this into `PATCH /api/cases/{case_id}` (USR-005).

        Validates and applies partial metadata updates (`title`, `icon_name`,
        `response_style`). The API layer delegates to this method so the
        per-field validation lives in the service, not the endpoint. The
        PATCH body is the new `UpdateCaseRequest` schema (USR-005) — not
        the old `RenameCaseRequest { title }` — so all three fields can be
        patched in a single request. Per-field validation (e.g.,
        `response_style` must be one of the three literals; `title` must
        be non-empty; `icon_name` must be in the allowed set) lives here.
        """
        case = cases.load(case_id, cases_path=self._cases_path)
        if case is None:
            raise KeyError(case_id)
        # ... validate fields, apply, save ...
        case.updated_at = _now()
        cases.save(case, cases_path=self._cases_path)
        return case

    async def delete_case(self, case_id: str) -> bool:
        # ISSUE-M3-006: acquire the per-case lock for the delete so a
        # concurrent `chat_structured` either runs strictly before or
        # strictly after the delete. (The in-flight call, if any, holds a
        # separate reference to the OLD lock and is not interrupted.)
        lock = await self._get_case_lock(case_id)
        async with lock:
            deleted = cases.delete(case_id, cases_path=self._cases_path)
        if deleted:
            await self._release_case_lock(case_id)
        return deleted

    async def get_history(self, case_id: str) -> list[ChatMessage]:
        # ISSUE-USR-007: thread cases_path through to `cases.load`.
        case = cases.load(case_id, cases_path=self._cases_path)
        return case.chat_history if case is not None else []


def _collect_tool_returns(new_messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Walk the current turn's `new_messages` and collect every `ToolReturnPart`.

    ISSUE-M3-002: this helper is non-trivial; spec'd here so the
    implementer doesn't have to invent it. We scan both `ModelRequest` and
    `ModelResponse` parts (the tool return is a request-side part for the
    next turn, but defensively scan both). ISSUE-USR-002: this MUST be
    called with `result.new_messages()` (current turn only) — never with
    `result.all_messages()`, which would include prior turns' tool returns
    and cause stale `deadline`/`template_letter`/`relevant_chunks` to leak
    into the adapter.
    """
    out: list[ToolReturnPart] = []
    for msg in new_messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                out.append(part)
    return out


def _truncate_history_to_turns(
    history: list[ModelMessage], max_turns: int
) -> list[ModelMessage]:
    """Slice `history` to the last `max_turns` user-turn groups.

    ISSUE-USR-003: a single turn that triggers a tool call emits 2-4
    `ModelMessage` objects (one `ModelRequest(parts=[UserPromptPart, ...])`,
    one `ModelResponse(parts=[TextPart, ToolCallPart])`, one or more
    `ModelRequest(parts=[ToolReturnPart])`). Slicing by raw message count
    can cut off a `ToolCallPart` while preserving its matching
    `ToolReturnPart`, producing an invalid provider history. Instead, we
    group messages into turns: a new turn begins at every
    `ModelRequest(parts=[UserPromptPart, ...])` (the user spoke), and any
    messages between user prompts belong to the prior turn. We keep only
    the last `max_turns` turn groups, so every tool call/return pair stays
    paired and we never feed the LLM an orphan `ToolReturnPart`.

    `max_turns < 1` returns an empty list (caller has already validated).
    """
    if max_turns < 1:
        return []
    if not history:
        return []

    # Walk backwards and count user-prompt turn boundaries. A turn group
    # starts at a ModelRequest whose first part is a UserPromptPart, OR
    # at a ModelRequest that contains a UserPromptPart (defensive). The
    # simplest correct heuristic: a turn boundary is any ModelRequest that
    # contains a UserPromptPart.
    turns: list[list[ModelMessage]] = []
    current_turn: list[ModelMessage] = []
    for msg in history:
        is_user_turn_start = (
            isinstance(msg, ModelRequest)
            and any(isinstance(p, UserPromptPart) for p in msg.parts)
        )
        if is_user_turn_start:
            if current_turn:
                turns.append(current_turn)
            current_turn = [msg]
        else:
            current_turn.append(msg)
    if current_turn:
        turns.append(current_turn)

    kept = turns[-max_turns:]
    out: list[ModelMessage] = []
    for t in kept:
        out.extend(t)
    return out


# ISSUE-IND-003: `_to_model_messages(chat_history) -> list[ModelMessage]`
# (previously spec'd here as a fallback when `model_history` was empty) is
# removed. `model_history` is ALWAYS populated on `Case` — initialized to
# `[]` on first creation (line 582) and appended on every subsequent turn
# (line 674). Empty list is a valid input to `_truncate_history_to_turns`
# (returns `[]`), so the helper was effectively unreachable. Defining it
# here as a "fallback" was misleading: no code path in the plan ever
# branched to it. The wire `ChatMessage` carries no `ToolCallPart`/
# `ToolReturnPart` payload, so any wire→model reconstruction would be
# lossy by design — better to surface "no LLM history yet" as the empty
# list it actually is. A future legacy-migration helper (if ever needed)
# would live in `storage/cases.py` alongside the migration shim, not here.
```

The `_backend` protocol stays as a simple `run(message, history) -> (prose, history)` (ISSUE-M3-003). The reviewer is called by `ChatService` exactly once per turn; the backend does not run it.

`AgentChatBackend` (refactored, no reviewer):
```python
class AgentChatBackend:
    """Implements `ChatBackend`. Does NOT run the reviewer — the service does."""

    def __init__(self, agent, deps_factory):
        self._agent = agent
        self._deps_factory = deps_factory

    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]:
        deps = self._deps_factory()
        result: AgentRunResult = await self._agent.run(
            message, deps=deps, message_history=history
        )
        prose = result.output  # the final assistant text
        # ISSUE-USR-002: return ONLY the current turn's new messages, not
        # the full `all_messages()` history. `all_messages()` includes the
        # input `message_history` and prior runs, which would cause prior
        # tool returns to leak into the adapter on this turn.
        new_messages = result.new_messages()
        return prose, new_messages
```

`build_chat_service(settings, deps_factory)` wires everything: `AgentChatBackend` + `ReviewerLike` (built from `tools.revisor.review_response`) + `ChatService`. **The `ChatService` constructor receives `cases_path=settings.cases_path`** (ISSUE-USR-007) so the `CASES_PATH` env var actually controls persistence. Without this injection, the env var would be silently ignored (the previous spec hardcoded `Path("./storage/cases")` inside `ChatService.__init__`).

### `src/advogado_de_bolso/api.py`
Major rewrite. Drop `/api/chat` and `/api/sessions`. Add the new case endpoints. Use **explicit SPA fallback** (not `StaticFiles(html=True)`). Return `422` for blocked responses.

**Endpoints:**
- `POST /api/chat/structured` (body: `StructuredChatRequest`) → `StructuredChatResponse` (200) **or** `{"blocked": true, "blocked_message": "..."}` (422) on reviewer block.
- `GET /api/cases` → `list[CaseSummary]`
- `GET /api/cases/{case_id}` → `CaseResponse` (added per ISSUE-USR-005 — required by tests and the frontend `handleSelectCase` flow, which was previously undocumented in the endpoint list). Delegates to `ChatService.get_case(case_id)`.
- `PATCH /api/cases/{case_id}` (body: `UpdateCaseRequest`) → `CaseResponse`. Delegates to `ChatService.update_case_meta` (ISSUE-M3-008 + ISSUE-USR-005) so per-field validation lives in the service. The body uses `UpdateCaseRequest { title?, icon_name?, response_style? }`, not the old `RenameCaseRequest { title }`. **This endpoint also serves the rename flow** (ISSUE-IND-002): the frontend's `apiClient.renameCase(caseId, newTitle)` is a thin client-side wrapper that calls `apiClient.updateCaseMeta(caseId, { title: newTitle })`, which issues a PATCH with `{ title }` to this same endpoint. There is no dedicated `rename_case` method on `ChatService`; the PATCH endpoint is the single metadata-update surface.
- `DELETE /api/cases/{case_id}` → 204
- `GET /api/cases/{case_id}/history` → `list[ChatMessage]`
- `GET /api/health` (kept)

**Dropped endpoints:** `POST /api/chat`, `DELETE /api/sessions/{session_id}`, `POST /api/cases` (per Open Issue #5 = A), `PUT /api/cases/{case_id}` (per Open Issue #14 = A).

**CORS:** `allow_methods = ["GET", "POST", "PATCH", "DELETE"]` (no PUT — removed). The current `api.py:92` has `allow_methods=["GET", "POST", "DELETE"]` and is missing `"PATCH"` (ISSUE-DS-004). Add it.

**Static serving:**
```python
# `api.py` lives at `<project_root>/src/advogado_de_bolso/api.py`, so:
#   .parent              → .../advogado_de_bolso/
#   .parent.parent       → .../src/
#   .parent.parent.parent → <project_root>          ← three parents
#   .parent.parent.parent.parent → one level ABOVE the project root (WRONG)
REACT_DIST = Path(__file__).parent.parent.parent / "base_frontend" / "dist"
```

```python
# Asset mount first (specific path)
if REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=REACT_DIST / "assets"), name="react-assets")

# SPA fallback: explicit, excludes /api and /assets. Use exact
# first-segment matching (ISSUE-009) so `/apiary` is NOT treated as
# `/api/...` and `/assetsManager` is NOT treated as `/assets/...`.
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    first_segment = full_path.split("/", 1)[0] if full_path else ""
    if first_segment in {"api", "assets"}:
        raise HTTPException(404, "Not Found")
    index = REACT_DIST / "index.html"
    if not index.exists():
        raise HTTPException(500, "Frontend bundle not built. Run `make frontend`.")
    return FileResponse(index)
```

This prevents the `StaticFiles(html=True)`-style behavior where `/api/chatt` (typo) returns 200 + `index.html` and the frontend breaks parsing JSON.

**Block envelope:** The `422` response body is `StructuredChatResponse` with `blocked=True`:
```python
# ISSUE-USR-008: `model_dump()` returns Python `date` objects from
# `DeadlineResult.data_inicio` / `data_limite`. Starlette's `JSONResponse`
# uses stdlib `json.dumps`, which raises `TypeError: Object of type date
# is not JSON serializable`. Use `model_dump(mode="json")` to coerce
# dates (and any other non-JSON-native types) to ISO-8601 strings.
# Alternatively, wrap the content with `jsonable_encoder` from
# `fastapi.encoders` — both are correct; `mode="json"` is preferred
# because it stays inside the Pydantic model layer.
if result.response.blocked:
    return JSONResponse(
        status_code=422,
        content=result.response.model_dump(mode="json"),
    )
return result.response
```

The API layer wraps `chat_structured` calls in a `try/except` and converts unhandled backend / save exceptions to `503 Service Unavailable` (ISSUE-M3-015). The frontend MUST parse the body on `!response.ok` to surface `blocked_message` to the user (ISSUE-DS-002).

### `src/advogado_de_bolso/cli.py`
Stays on `agent.run_stream` (per Open Issue #1 = A). Writes case files via the storage layer directly.

- Build the agent once via `build_agent(settings)`.
- Build a `KnowledgeIndex` and `Deps` as today.
- Use a per-CLI-session `model_history: list[ModelMessage]` (in-memory).
- After each turn, save the case file to `./storage/cases/{session_id}.json` — **the same path the API uses** (ISSUE-010) so CLI conversations are visible from the UI and vice versa.
- The CLI constructs a `Case` object with both `chat_history` and `model_history` populated, then calls `cases.save(case, cases_path=settings.cases_path)` (ISSUE-DS-010 + ISSUE-USR-007). Saving only `chat_history` would leave `model_history == []` on disk, and a subsequent API turn on the same case would lose tool-call/return context (per ISSUE-M3-001). The persistence path is shared with the API, so the saved shape must match. The CLI reads `settings.cases_path` (env `CASES_PATH`) so the env var works for both transports.
- Streaming UX preserved (the Live spinner / token-by-token rendering at `cli.py:124-156`).

### `src/advogado_de_bolso/config.py`
Add `cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")` (ISSUE-M3-014). The env alias keeps `Settings` consistent with `DATA_PATH` / `CHROMA_PATH` / `HF_HOME` which all use `Field(..., alias=...)`.

### `src/advogado_de_bolso/deps.py`
**No changes.** Per Open Issue #5 and #11: `response_style` does NOT live on `Deps`. The `@agent.instructions` callback reads from `_current_style` (a `ContextVar`). The ContextVar is task-local and is reset by `chat_structured`'s `try/finally` (ISSUE-DS-008). Sub-agents in this codebase (`redigir_documento`, `revisar_resposta`) do NOT read `_current_style` and are safe. If a future sub-agent needs style awareness, it must be passed explicitly via `ctx.deps`, not via the ContextVar.

### `tests/test_adapter.py` (new)
Golden tests covering:
- DeadlineResult turn → `structured.deadline` populated.
- DraftedDocument turn → `structured.template_letter == doc.texto`.
- Both in one turn → both populated.
- search_knowledge_base empty list → no `relevant_content`, no error.
- search_knowledge_base with chunks → `relevant_title` = first `fonte`, `relevant_content` = joined first two `texto`s.
- search_knowledge_base returning a `tuple` (Sequence) → accepted (ISSUE-M3-010).
- `calcular_prazo_consumidor` returning a **string** (error path) → `structured.deadline is None`, no crash.
- Reviewer-blocked case → `structured.blocked is True`, `structured.blocked_message` is set.
- `prose` containing "Posso..." questions → `questions` is non-empty.
- **`prose` with "Posso cancelar a compra?"** (ISSUE-USR-010): assert the extracted question is `"Posso cancelar a compra?"` (or the rstrip'd form `"Posso cancelar a compra"` with the trailing `?` re-appended by the helper), NOT `"Posso"`. Pins the regex fix.
- **`prose` with "1. The customer should..."** (ISSUE-USR-010): assert the numbered list item is NOT extracted as a question (the new pattern requires the item to end in "?"). Pins the regex fix for non-question numbered items.
- `prose` with no patterns → `questions = []`, `quick_replies` falls back to defaults.
- **Empty prose** → `step_title == "Análise inicial"`, `step_content == ""` (ISSUE-004).
- **Unknown tool name** in the `ToolReturnPart.tool_name` → the `else` branch logs a WARNING; no exception raised; `structured` is otherwise unchanged (ISSUE-DS-006).
- **`tool_plain` raw-object contract** (ISSUE-006 + ISSUE-USR-009): the test MUST exercise the **real Pydantic AI tool-execution path**, not a hand-constructed `ToolReturnPart`. The previous spec ("construct a fake `ToolReturnPart` whose `content` is a `DeadlineResult` instance, assert `isinstance(part.content, DeadlineResult)`") was tautological — it only proved Python can hold a reference to a typed object inside a dataclass field. The new spec:
  1. Register a real `@agent.tool_plain` function that returns a `DeadlineResult` (e.g., a stub `def stub_calcular(...) -> DeadlineResult: return DeadlineResult(...)`).
  2. Call `await agent.run("user message that triggers the tool")` against a real (or `TestModel`) LLM.
  3. Inspect `result.new_messages()` and assert the last `ModelResponse.parts[-1]` is a `ToolCallPart` AND the immediately-following `ModelRequest.parts[-1]` is a `ToolReturnPart` whose `content` is an **`isinstance` of `DeadlineResult`** (NOT a `dict`).
  4. This pins the actual `tool_plain` → `ToolReturnPart` round-trip. If Pydantic AI changes and starts stringifying `tool_plain` returns, this test will fail loudly.
  5. Note: even with the real round-trip, JSON serialize/deserialize (`all_messages_json` → `ModelMessagesTypeAdapter.validate_python`) will produce a plain `dict` from the typed object on reload — the test therefore only pins the **in-memory** behavior, not persistence. A separate test pins the persistence shape (typed content survives `case.model_history` round-trip through the storage layer).

### `tests/test_storage.py` (new)
- Atomic write (write to `.tmp`, replace).
- `delete_case` removes the file and the lock.
- `list_all` returns the right summaries.
- Missing file → `load` returns `None`, not raise.

### `tests/test_calculos.py` (rewrite)
All string-content assertions become field assertions:
- `assert result.tipo_prazo == "arrependimento"`
- `assert result.dias == 7`
- `assert result.base_legal == "CDC art. 49"`
- For error cases, assert `isinstance(result, str)` and substring matches.

### `tests/test_redigir.py` (rewrite)
- Mock the sub-agent to return a string.
- Assert the outer `redigir_documento` returns a `DraftedDocument`.
- Assert `result.tipo == <input>`, `result.tom == <input>`, `result.destinatario == <input>`, `result.texto == "texto gerado..."`.

### `tests/test_rag_tool.py` (rewrite)
- Mock the retriever to return nodes.
- Assert `search_knowledge_base` returns `list[KnowledgeChunk]`.
- Assert the first chunk's `fonte` is the node's `file_name`.
- Empty result → `[]` (preserved in `KnowledgeChunk` form, or sentinel if needed).

### `tests/test_api.py` (rewrite)
- Drop tests for `/api/chat`, `/api/sessions/{id}`, `/assets/*`.
- Add tests for `/api/chat/structured` (200 success, 422 blocked, 422 validation error).
- Add tests for `GET /api/cases`, `GET /api/cases/{id}`, `PATCH /api/cases/{id}`, `DELETE /api/cases/{id}`, `GET /api/cases/{id}/history`.
- Add a test for the SPA fallback (`GET /` returns index.html, `GET /api/typo` returns 404).
- **PATCH body test** (ISSUE-USR-005): assert that `PATCH /api/cases/{id}` with `UpdateCaseRequest { title: "X" }`, `{ icon_name: "shopping_bag" }`, `{ response_style: "simples" }`, and any combination thereof, all succeed; assert that an empty body `{ }` returns 422 (the `model_validator` rejects "no fields set"); assert that an unknown field returns 422.
- **GET single-case test** (ISSUE-USR-005): assert `GET /api/cases/{id}` returns a `CaseResponse` for an existing case and 404 for a missing case.
- **Blocked-first-message test** (ISSUE-USR-004): assert that a blocked first message returns 422, the response body includes `session_id` and `blocked_message`, and NO `{session_id}.json` file is created on disk (the service skips `cases.save` for blocked new cases).

### `tests/test_service.py` (rewrite)
- `ChatService` no longer has `chat`, `clear_session`, `session_history`, `session_count`, `_max_sessions`, `_evict_old_sessions`.
- New tests: `chat_structured` with new session creates a case file; second message appends; per-case lock serializes concurrent calls; reviewer-blocked returns blocked; `delete_case` cleans up the lock.
- Test the `ContextVar` reset: after `chat_structured(style="simples")`, the style is reset (no leakage between requests).
- **`model_history` persistence** (ISSUE-M3-001): after a turn that included a `ToolCallPart`/`ToolReturnPart`, the case file on disk contains the full `ModelMessage` list with the tool parts. A subsequent `chat_structured` call passes that list back to the backend. Assert via inspecting `case.model_history` after the first call, then mock the second call to capture the `history` argument and assert it matches.
- **`update_case_meta` wiring** (ISSUE-M3-008): the PATCH endpoint calls `update_case_meta(case_id, title="...")`, and the case on disk reflects the new title. Title validation (non-empty, max length) lives in `update_case_meta`, not the endpoint.
- **Lock cleanup race** (ISSUE-M3-006): after `delete_case`, the case_id is no longer in `_case_locks`. A subsequent `chat_structured` for the same id creates a new lock cleanly.

### `tests/test_agent.py` (extend)
- Existing test stays.
- Add: `test_build_agent_registers_style_instructions` — assert the agent has an instructions function registered.
- Add: `test_context_var_resets_after_request` (ISSUE-DS-008) — after `chat_structured(style="simples")` returns, `_current_style.get()` is `None` again (no leakage to the next request). Use a real `ChatService` with a fake `ChatBackend` and a fake `ReviewerLike`.
- Add: `test_context_var_visible_inside_chat_structured` (ISSUE-DS-008) — inside the backend call, `_current_style.get()` returns the value passed to `chat_structured`. Pins the in-request propagation.

### `Makefile`
```makefile
frontend:    cd base_frontend && npm ci && npm run build
dev-api:     uv run advogado-api
dev-frontend: cd base_frontend && npm run dev
dev:         make -j2 dev-api dev-frontend
```

### `base_frontend/src/api.ts` (new)
Thin HTTP client + snake↔camel mapper:
- `mapStructuredResponse(payload, sessionId): ChatMessage` — maps the server response to a UI `ChatMessage`, sets `tagText` from `deadline`/`templateLetter` truthiness, derives `date` from `updated_at` ("Hoje" | "Ontem" | "DD MMM").
- `mapCaseSummary(payload): Case` — maps `CaseSummary` to UI `Case`, derives `date` from `updated_at`.
- `chatStructured`, `listCases`, `getCase`, `renameCase`, `deleteCase`, `getHistory`.
- `renameCase(caseId, newTitle)` (ISSUE-IND-002) is a **thin wrapper** around `updateCaseMeta(caseId, { title: newTitle })`: it PATCHes `/api/cases/{case_id}` with `{ title: newTitle }` and the server-side `update_case_meta` does the work. There is no dedicated `renameCase` REST endpoint; the PATCH is the single metadata-update surface. `handleRenameCase` in `App.tsx` calls this wrapper.

### `base_frontend/src/defaults.ts` (new)
- `initialPreferences` (moved from `App.tsx`).
- `seedCases: Case[]` — the three demo cases, each with `is_demo: true` and a `tagText: "DEMO"`.

---

## Files to Modify

### `src/advogado_de_bolso/tools/calculos.py`
Return `DeadlineResult` for successful calculations; keep returning `str` for error paths (missing `tipo_item`, invalid date, invalid `tipo_prazo`). The system prompt instructs the LLM to relay the error string to the user.

### `src/advogado_de_bolso/tools/redigir.py`
Return `DraftedDocument` with `tom: Tom` literal (imported from existing `Tom = Literal[...]` at `tools/redigir.py:24`). Update the docstring to declare the new return shape. Update the sub-agent's user prompt to remove the "Responda APENAS com o texto final" instruction (the sub-agent is now wrapped into a structured envelope, but its actual output is still the prose — see Open Decision #1 below).

### `src/advogado_de_bolso/tools/rag.py`
Return `list[KnowledgeChunk]`. Preserve the "fonte desconhecida" fallback. Preserve the "no results" signal — when the retriever returns nothing, return a single `KnowledgeChunk(fonte="sistema", texto="Nenhum trecho relevante foi encontrado na base de conhecimento.")` so the LLM has an explicit "no results" hint. Update the docstring.

### `src/advogado_de_bolso/agent.py`
See "Files to Create" section above. Add `@agent.instructions` callback. Update `SYSTEM_PROMPT` to describe the new tool return shapes. Add `STYLE_PROMPTS` and `_current_style` ContextVar.

### `src/advogado_de_bolso/service.py`
See "Files to Create" section above. Drop `chat`, `clear_session`, `session_history`, `session_count`, `_max_sessions`, `_evict_old_sessions`, `_max_history_messages`. Add `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history` (`rename_case` removed per ISSUE-IND-002 — the PATCH endpoint delegates to `update_case_meta`, and a single-field rename is just `update_case_meta(case_id, title=new_title)`). Add per-case `asyncio.Lock` registry. Add `StructuredChatResponse` dataclass (renamed from `ChatReply`). 20-turn cap on LLM-bound history.

### `src/advogado_de_bolso/api.py`
See "Files to Create" section above. Drop the old endpoints. Add the new ones. Use explicit SPA fallback. Return 422 for blocked.

### `src/advogado_de_bolso/cli.py`
See "Files to Create" section above. Keep `agent.run_stream`. Write case files to `./storage/cases/` (same as API per ISSUE-010). Streaming UX preserved.

### `src/advogado_de_bolso/config.py`
Add `cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")` (ISSUE-M3-014). The env alias keeps `Settings` consistent with `DATA_PATH` / `CHROMA_PATH` / `HF_HOME` which all use `Field(..., alias=...)`. **Also ensure the value is wired into the service via `build_chat_service(settings, deps_factory)` → `ChatService(..., cases_path=settings.cases_path)`** (ISSUE-USR-007); without that injection the env var is dead.

### `tests/test_calculos.py`
Rewrite (see above).

### `tests/test_redigir.py`
Rewrite (see above).

### `tests/test_rag_tool.py`
Rewrite (see above).

### `tests/test_api.py`
Rewrite (see above).

### `tests/test_service.py`
Rewrite (see above).

### `tests/test_agent.py`
Extend (see above).

### `base_frontend/package.json`
ISSUE-M3-004: full rewrite. The current `package.json` references `server.ts` in FOUR scripts (`dev`, `build`, `start`, `clean`). After the file deletion, every one of these breaks. The full set of changes:

- `"dev"`: `"vite"` (was `"tsx server.ts"`)
- `"build"`: `"vite build"` (was `"vite build && esbuild server.ts --bundle --platform=node --format=cjs --packages=external --sourcemap --outfile=dist/server.cjs"`)
- `"start"`: **REMOVED** (the FastAPI server now serves the build in prod; a separate Node `start` is redundant)
- `"clean"`: `"rimraf dist"` or `"rm -rf dist"` (was `"rm -rf dist server.js"`)
- `"preview"`: `"vite preview"` (kept; useful for testing the prod build)
- `"lint"`: `"tsc --noEmit"` (kept)
- Remove `dependencies`: `@google/genai`, `express`, `dotenv`, `motion` (all consumed only by the deleted `server.ts`)
- Remove `devDependencies`: `tsx`, `esbuild`, `@types/express`, `@types/node` (consumed only by the deleted `server.ts`)
- Environment variables `GEMINI_API_KEY` and the Express-specific `PORT` are no longer used; the FastAPI server reads its own env (`GOOGLE_API_KEY`, `ADVOGADO_API_HOST`, `ADVOGADO_API_PORT`).

### `base_frontend/vite.config.ts`
ISSUE-DS-003: add `server.proxy = { "/api": "http://localhost:8000" }` so dev mode (Vite on :5173) can reach the FastAPI server on :8000. Also tighten the `server` block:
```ts
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
    hmr: { /* existing settings */ },
    watch: { /* existing settings */ },
  },
});
```

### `base_frontend/src/App.tsx`
ISSUE-M3-016: explicitly **delete** the inline `seedCases` (lines 20-130, ~110 lines) and `initialPreferences` (lines 132-144). The plan said "move to `defaults.ts`" but the deletion must be explicit. After the move, `App.tsx` imports them:
```ts
import { seedCases, initialPreferences } from "./defaults";
```
- The `is_demo: true` flag on each seed case stays frontend-only (ISSUE-M3-005). The server never sets `is_demo: true`. `CaseSummary.is_demo` is reserved for future server-side template cases and is not used today.
- Add `useState<boolean>(true)` for `isLoadingCases` (ISSUE-M3-017). On mount, call `apiClient.listCases()`. While loading, show a spinner; when done, render the list.
- **Rename** the existing `isLoading` (per-message chat spinner) to `isSendingMessage` (ISSUE-M3-017). Update `ChatInterface` props to use `isSendingMessage`. The two loading flags now have unambiguous names.
- `handleSendMessage`:
  - If `activeCaseId === null`, this is the first message of a new case. Compute `title` and `icon_name` from the message text (current keyword logic from `App.tsx:296-340`). Send `{message, session_id: null, response_style, title, icon_name}` to `POST /api/chat/structured` (ISSUE-DS-005: NOT `/api/chat`, which is deleted).
  - On response, set `activeCaseId = resData.session_id`.
  - **Error handling** (ISSUE-DS-002 + ISSUE-USR-004): if `!response.ok`, parse the body. If `body.blocked === true`, display `body.blocked_message` to the user via the chat (not a generic error). Capture `body.session_id` from the 422 body if present, store it in a ref (e.g., `pendingBlockedCaseIdRef`), and — on the next send — reuse it as the `session_id` for the retry. This avoids orphan cases on blocked first messages (the server already skipped `cases.save` for blocked-new-case per ISSUE-USR-004, but if any old code path persists the blocked case, the client must still pin the id to prevent duplicates).
- `handleSaveCaseFromChat`:
  - Fires the PATCH **only when the user has manually edited the title/icon AND the case already exists server-side** (ISSUE-M3-013). The first-message auto-create flow does NOT trigger a save PATCH because the title/icon are already in the request body that the server just used to create the case.
  - Sends a single `PATCH /api/cases/{case_id}` with the new `UpdateCaseRequest` body `{ title?, icon_name?, response_style? }` (ISSUE-USR-005). The `apiClient` exposes one `updateCaseMeta(caseId, fields)` method that accepts a partial `UpdateCaseRequest` payload; the client omits unset fields. The previous two-call approach (`renameCase` + `updateCaseMeta`) is collapsed into one call.
- `handleSelectCase` → `apiClient.getCase(caseId)`.
- `handleDeleteCase` → `apiClient.deleteCase(caseId)`.
- `handleRenameCase` → `apiClient.renameCase(caseId, newTitle)`, which under the hood calls `apiClient.updateCaseMeta(caseId, { title: newTitle })` and issues `PATCH /api/cases/{case_id}` with `{ title }` (ISSUE-IND-002). There is no dedicated `renameCase` REST endpoint; the frontend rename is a PATCH with a `{ title }` body.
- The `history` field in the request body is removed (server is now the source of truth; the server returns the full chat history with each response).
- Filter out `is_demo` cases when the first real case is created (clear them from local state, never re-add).

### `base_frontend/src/types.ts`
- Add `is_demo?: boolean` to `Case` (ISSUE-M3-005). Frontend-only marker.
- `iconName` union unchanged (4 hardcoded values).
- `date: string` stays — client-derived by the mapper.

### `base_frontend/src/defaults.ts` (new, additional spec)
- `initialPreferences` (moved from `App.tsx` lines 132-144).
- `seedCases: Case[]` — the three demo cases, each with `is_demo: true` and a `tagText: "DEMO"`. These are the **only** `is_demo: true` cases in the system. The server never produces one.

---

## Files to Delete

- `base_frontend/server.ts`

---

## Verification

### Implementation order (ISSUE-M3-018)
Tests cannot pass during a partial implementation. To gate progress, the implementation MUST follow this order, with `pytest` green at the end of each step:

1. Add `src/advogado_de_bolso/contracts.py` (the new typed envelopes).
2. Refactor `src/advogado_de_bolso/tools/calculos.py` to return `DeadlineResult | str`.
3. Refactor `src/advogado_de_bolso/tools/redigir.py` to return `DraftedDocument`.
4. Refactor `src/advogado_de_bolso/tools/rag.py` to return `list[KnowledgeChunk]`.
5. Rewrite `tests/test_calculos.py`, `tests/test_redigir.py`, `tests/test_rag_tool.py` to assert on the new types. **Run `pytest` — must be green.**
6. Add `src/advogado_de_bolso/storage/__init__.py` and `src/advogado_de_bolso/storage/cases.py` with the directory-creation spec.
7. Add `tests/test_storage.py`. **Run `pytest` — must be green.**
8. Add `src/advogado_de_bolso/schemas.py` (wire types).
9. Add `src/advogado_de_bolso/adapter.py` plus the three helper functions (`_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`).
10. Add `tests/test_adapter.py`. **Run `pytest` — must be green.**
11. Add `Settings.cases_path` (with `alias="CASES_PATH"`) in `src/advogado_de_bolso/config.py`.
12. Rewrite `src/advogado_de_bolso/agent.py` with the new `SYSTEM_PROMPT`, `STYLE_PROMPTS`, `_current_style` ContextVar, and `@agent.instructions` callback.
13. Rewrite `src/advogado_de_bolso/service.py` with the new `ChatService`, `ChatResult`, helper functions, per-case locks, and `model_history` persistence.
14. Rewrite `src/advogado_de_bolso/api.py` with the new endpoints, SPA fallback, and CORS.
15. Rewrite `tests/test_service.py` and `tests/test_api.py`. **Run `pytest` — must be green.**
16. Add `tests/test_agent.py` extension for `STYLE_PROMPTS` / `_current_style` / ContextVar scoping (ISSUE-DS-008).
17. Frontend: clean up `base_frontend/package.json` (full script and dep rewrite).
18. Frontend: add `server.proxy` to `base_frontend/vite.config.ts`.
19. Frontend: add `src/api.ts` and `src/defaults.ts`; refactor `App.tsx` (delete inline `seedCases`/`initialPreferences`, rename `isLoading` → `isSendingMessage`, add `isLoadingCases`, update endpoint, add blocked-message parsing).
20. Delete `base_frontend/server.ts`. **Run `npm run lint` (tsc) — must be green.**

Do not move to step N+1 until step N's tests are green.

### Functional checks
1. `uv run pytest` — all tests pass.
2. `uv run ruff check src/` and `uv run mypy src/` — clean.
3. `cd base_frontend && npm run lint` (tsc) — clean.
4. **Dev mode**: `uv run advogado-api` on :8000; `cd base_frontend && npm run dev` on :5173.
5. **UI smoke**: send "Comprei um celular online e me arrependi" → deadline card, CDC art. 49, quick replies. First message auto-creates the case with title="Celular comprado online" and icon_name="shopping_bag".
6. **Persistence**: create case, restart server, refresh → case still in list with history (and `model_history` is intact, so turn-2 follow-ups retain tool-call context per ISSUE-M3-001).
7. **CRUD**: PATCH (rename), DELETE, list, select — all reflect immediately.
8. **Style switching**: change `responseStyle` to `simples` → plainer prose. Verify the `_current_style` ContextVar is reset (no leakage between requests).
9. **Reviewer block**: temporarily block → API returns 422 with `{"blocked": true, "blocked_message": "..."}`; frontend `handleSendMessage` parses the body and shows `blocked_message` to the user (ISSUE-DS-002).
10. **Demo cases**: on first load, three demo cases appear with a "DEMO" badge. After the first real case is created, demo cases disappear from the list.
11. **Production**: `make frontend` then `uv run advogado-api` → React on :8000.
12. **CORS**: PATCH/DELETE work from Vite on :5173 (allow_methods includes `"PATCH"` per ISSUE-DS-004).
13. **CLI**: `uv run advogado` → streaming spinner works, case file written to `./storage/cases/` (same path as API per ISSUE-010). The CLI-created case is visible from the UI.
14. **API typo**: `GET http://localhost:8000/api/chatt` → 404 (not 200 + HTML). Exact first-segment check per ISSUE-009.
15. **Lock cleanup**: create a case, delete it, immediately create a new case with the same id → no lock leak (ISSUE-M3-006).
16. **Empty prose**: agent returns empty string → `step_title = "Análise inicial"`, `step_content = ""` (ISSUE-004).
17. **Unknown tool name**: tool returns content with an unexpected `tool_name` → logged at WARNING, not raised (ISSUE-DS-006).

---

## Resolved Open Decisions

### 1. `redigir_documento` JSON envelope in LLM context — **RESOLVED**
- **Tool docstring** updated to declare `DraftedDocument` return shape with `texto` as the body.
- **Sub-agent user prompt** at `redigir.py:101-104` is **kept** ("Responda APENAS com o texto final"). The sub-agent is a **plain string producer**; the outer `redigir_documento` function wraps its output into a `DraftedDocument` envelope (filling `tipo`/`tom`/`destinatario` from the function's own arguments). The sub-LLM does NOT need to produce JSON; only the outer Python wrapper does.
- **Main agent system prompt** at `agent.py` updated: "When `redigir_documento` returns, it gives you a JSON object with `tipo`, `tom`, `destinatario`, and `texto`. Present only the `texto` field to the user as the document body. Do not paraphrase or summarize it."
- **Contract test** in `test_adapter.py`: a redigir turn produces `structured.template_letter == doc.texto`.

### 2. `PUT` vs `PATCH` for rename — **RESOLVED: PATCH only**
- One endpoint: `PATCH /api/cases/{case_id}` with `UpdateCaseRequest { title?, icon_name?, response_style? }` (a single-field rename is just `UpdateCaseRequest { title }`).
- REST-correct (partial update).
- The Open Decision "PUT for full replacement" is deferred until there's a UI consumer for it.
- Originally specified as `RenameCaseRequest { title }`; expanded to `UpdateCaseRequest` per ISSUE-USR-005 to also carry `icon_name` and `response_style` in the same PATCH.

### 3. Plan-level fixes applied (round 3 of the implementation-review-fix loop)
The following reviewer issues were applied directly to this plan. Each is referenced in the section it touches. See `.opencode/loop/open-issues.md` for full context.

| Issue | Fix |
|-------|-----|
| ISSUE-001 | `REACT_DIST` path uses 3 `.parent` calls (was 4). |
| ISSUE-002 | Renamed service-layer wrapper to `ChatResult` (was self-named `StructuredChatResponse`). |
| ISSUE-003 | Spec'd `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies` in adapter.py. |
| ISSUE-004 | Empty-prose fallback filters whitespace-only paragraphs. |
| ISSUE-005 | `cases.save()` calls `mkdir(parents=True, exist_ok=True)`. |
| ISSUE-006 | Added `tests/test_adapter.py` contract test for `tool_plain` raw-object round-trip. |
| ISSUE-008 | User/assistant messages use distinct timestamps. |
| ISSUE-009 | SPA fallback uses `first_segment in {"api", "assets"}`. |
| ISSUE-010 | CLI writes to `./storage/cases/` (same as API). |
| ISSUE-011 | Full merged `SYSTEM_PROMPT` provided (replaced bullet excerpts). |
| ISSUE-M3-001 | Added `model_history: list[ModelMessage]` to `Case`. |
| ISSUE-M3-002 | Spec'd `_collect_tool_returns` in service.py; `_to_model_messages` removed entirely (ISSUE-IND-003) because no caller materialized — `model_history` is always populated on `Case`. |
| ISSUE-M3-003 | Refactored `AgentChatBackend` shown without reviewer; `ChatService` runs reviewer exactly once. |
| ISSUE-M3-004 | Full `package.json` rewrite spec'd (dev/build/start/clean + dep removal). |
| ISSUE-M3-005 | `is_demo` documented as frontend-only marker. |
| ISSUE-M3-006 | `delete_case` acquires per-case lock before deleting. |
| ISSUE-M3-007 | `response_style` semantics clarified: persisted as case default + per-request override. |
| ISSUE-M3-008 | `update_case_meta` wired into `PATCH /api/cases/{case_id}`. |
| ISSUE-M3-009 | Replaced line numbers with type/method references. |
| ISSUE-M3-010 | Adapter uses `isinstance(content, (list, tuple))`. |
| ISSUE-M3-011 | Dropped `TypeAdapter.validate_python` redundant call. |
| ISSUE-M3-012 | `SYSTEM_PROMPT` now treats `fonte="sistema"` as the no-results signal. |
| ISSUE-M3-013 | `handleSaveCaseFromChat` PATCH fires only on manual edit. |
| ISSUE-M3-014 | `cases_path` uses `Field(..., alias="CASES_PATH")`. |
| ISSUE-M3-015 | Error contract: API catches backend/save exceptions, returns 503. |
| ISSUE-M3-016 | Explicit "delete inline `seedCases`/`initialPreferences`" added to App.tsx section. |
| ISSUE-M3-017 | `isLoading` renamed to `isSendingMessage`; new `isLoadingCases`. |
| ISSUE-M3-018 | 20-step ordered implementation with per-step `pytest` gate. |
| ISSUE-DS-001 | `_now()` defined at module scope. |
| ISSUE-DS-002 | Frontend `handleSendMessage` parses body and surfaces `blocked_message`. |
| ISSUE-DS-003 | `vite.config.ts` `server.proxy` fully spec'd. |
| ISSUE-DS-004 | CORS `allow_methods` includes `"PATCH"`. |
| ISSUE-DS-005 | Frontend uses `/api/chat/structured` with new body shape. |
| ISSUE-DS-006 | Adapter logs WARNING for unknown tool names. |
| ISSUE-DS-007 | `list_all()` scalability constraint in docstring + soft warning at 500+ files. |
| ISSUE-DS-008 | ContextVar scoping test added; single-task assumption documented. |

---

## Out-of-Scope Notes

- **Multi-worker `uvicorn`**: not supported. The plan assumes a single worker. Multi-worker would break the in-process `asyncio.Lock` registry and the `_current_style` ContextVar. Document in README.
- **`_index.json`**: not built. `list_all()` scans the directory. Acceptable for the expected scale (<1000 cases, per ISSUE-DS-007 — the constraint is documented in the `storage/cases.py` module docstring and in the project README; a soft `INFO` log fires when the file count exceeds 500). If the scale grows, add a startup disk-scan-rebuild index (not planned now).
- **Auth / multi-user**: not in scope. The plan assumes a single local user.
- **Streaming for the API**: not in scope. The plan's `POST /api/chat/structured` is request/response. The CLI keeps streaming via `agent.run_stream` directly.
- **Single-task ContextVar scoping** (ISSUE-DS-008): `_current_style` is a `ContextVar` reset by `chat_structured`'s `try/finally`. It propagates task-locally to any sub-agent run in the same `await` chain. Today no sub-agent reads `_current_style`, so the coupling is safe. If a future sub-agent needs style awareness, it MUST receive the style via `ctx.deps`, not via the ContextVar. The `tests/test_agent.py` extension includes a scoping test that runs a fake sub-agent and asserts the parent ContextVar does not leak after `chat_structured` returns.
- **Sub-agent LRU cache**: the drafting and reviewer sub-agents are cached at module scope (existing pattern at `tools/redigir.py:60`). They are created once and never read `_current_style`. This is the primary mitigation for ISSUE-DS-008.
