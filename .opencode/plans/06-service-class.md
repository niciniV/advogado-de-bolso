# 06-service-class.md

**Source plan:** revised-integration-plan.md (split round 19, lines 394-805; 412 content lines + ~5-line header)
**In this file:** `src/advogado_de_bolso/service.py` — `ChatService` class with `__init__`, `_get_case_lock`, `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history`; also the `REVIEW_BLOCKED_MESSAGE` constant, `_now`/`_now_ms` helpers, `ChatResult` dataclass, and `ChatBackend`/`ReviewerLike` Protocols. Splits at the natural class-boundary just before `_collect_tool_returns` (which lives in `07-service-helpers-and-backend.md`).
**Related files:** [07-service-helpers-and-backend.md](./07-service-helpers-and-backend.md) (module-scope helpers `_collect_tool_returns`, `_truncate_history_to_turns`, `AgentChatBackend`, `build_chat_service` notes), [04-storage.md](./04-storage.md) (the `cases_path` injected into the service), [02-schemas.md](./02-schemas.md) (the `ChatResult.response` field is a `StructuredChatResponse`).

### `src/advogado_de_bolso/service.py`
Major rewrite. `ChatService.chat_structured` is the new primary method. No `_max_sessions` (disk is the source of truth). No `_max_history_messages` cap on persistence, but a **20-turn cap on the LLM-bound slice** (per Open Issue #9 = A).

```python
from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from contextvars import Token
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol
# ISSUE-USR-001: `UUID` is used to type `chat_structured(session_id)`
# so the service signature matches the Pydantic-validated
# `StructuredChatRequest.session_id: UUID | None`. Pydantic rejects
# malformed UUIDs with 422 at the API layer.
from uuid import UUID

from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
    UserPromptPart,
)
# ISSUE-USR-011: `AgentRunResult` is re-exported from the top-level
# `pydantic_ai` package (and also from `pydantic_ai.run`). The previous
# import path `from pydantic_ai.tools import AgentRunResult` raises
# `ImportError: cannot import name 'AgentRunResult' from 'pydantic_ai.tools'`
# on pydantic_ai 1.106.0 (and on the 1.x line in general). The class
# lives in `pydantic_ai.run`, but the public re-export is at the package
# root, so we import from there to stay forward-compatible.

from . import schemas
from .adapter import extract_structured_response
# `_current_style` carries the request-local response style read by agent instructions.
from .agent import _current_style
from .deps import Deps
from .schemas import CaseSummary, ChatMessage
from .storage import cases
# ISSUE-USR-006: `Case` is the persistent storage model defined in
# `storage/cases.py` (see plan line 259), NOT in `schemas.py` (which only
# defines the wire types `CaseResponse`, `CaseSummary`, `ChatMessage`,
# `UpdateCaseRequest`, `StructuredChatRequest`, `StructuredChatResponse`).
# The previous import `from .schemas import Case` would raise
# `ImportError: cannot import name 'Case' from 'advogado_de_bolso.schemas'`
# at import time. Import from the storage module instead.
from .storage.cases import Case
from .tools.revisor import RevisionResult

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
            # Load or create the in-memory case. A blocked turn returns before
            # any mutation/save, so a blocked first message creates no file.
            case = cases.load(case_id, cases_path=self._cases_path)
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
            # Existing cases intentionally ignore title/icon_name supplied
            # with chat requests. Metadata changes only through
            # PATCH /api/cases/{case_id}.

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

                # A blocked turn is not part of either persisted history.
                # Do not expose rejected prose/tool outputs, and do not append
                # rejected new_messages to model_history. Return the existing
                # persisted chat snapshot plus the safe blocked message only.
                if blocked:
                    structured = extract_structured_response(
                        blocked_message or "", [],
                        blocked=True, blocked_message=blocked_message,
                    )
                    structured.session_id = case_id
                    structured.chat_history = list(case.chat_history)
                    structured.updated_at = case.updated_at
                    return ChatResult(session_id=case_id, response=structured)

                # Extract structured data — inspect ONLY the approved current
                # turn's tool returns. Prior turns' returns live in
                # case.model_history and are NOT re-examined (ISSUE-USR-002).
                tool_returns = _collect_tool_returns(new_messages)
                structured = extract_structured_response(prose, tool_returns)
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

                # Overwrite the response model's assembly-safe defaults with
                # the actual persisted case snapshot. `chat_history` is a
                # defensive shallow copy; FastAPI serializes `updated_at`.
                structured.chat_history = list(case.chat_history)
                structured.updated_at = case.updated_at

                # Only approved turns reach this point. `cases.save` is called
                # before returning; save failures propagate to the API layer,
                # which converts them to 503. Blocked turns returned above
                # without mutating chat_history or model_history.
                cases.save(case, cases_path=self._cases_path)

                return ChatResult(session_id=case_id, response=structured)
            finally:
                _current_style.reset(style_token)

    async def list_cases(self) -> list[CaseSummary]:
        # ISSUE-USR-007: thread the configured cases_path through to the
        # storage layer.
        return cases.list_all(cases_path=self._cases_path)

    async def get_case(self, case_id: UUID) -> Case | None:
        # ISSUE-USR-007: thread cases_path through to `cases.load`.
        return cases.load(str(case_id), cases_path=self._cases_path)

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
        self, case_id: UUID, **fields: Any
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

        ISSUE-USR-013: this method MUST acquire the per-case lock before
        loading and saving the case. Without the lock, a concurrent
        `chat_structured` on the same `case_id` could read the case, then
        this method could read-modify-save the same case, and one of the
        two writes would clobber the other. The lock-registry invariant
        (one lock per state-modifying case operation) is preserved by
        mirroring `delete_case`'s pattern at line 768: acquire the lock,
        do the load/validate/save, and release implicitly via the
        `async with` exit. The lock object remains in the registry for the
        service lifetime so every future operation for this UUID continues
        to serialize on the same object.
        """
        # ISSUE-USR-013: acquire the per-case lock to serialize metadata
        # updates with concurrent `chat_structured` and `delete_case` on
        # the same case_id. The same `asyncio.Lock` instance is reused
        # for all state-modifying operations on this case.
        case_key = str(case_id)
        lock = await self._get_case_lock(case_key)
        async with lock:
            case = cases.load(case_key, cases_path=self._cases_path)
            if case is None:
                raise KeyError(case_key)

            allowed_fields = {"title", "icon_name", "response_style"}
            unknown = set(fields) - allowed_fields
            if unknown:
                raise ValueError(f"Unknown case metadata fields: {sorted(unknown)}")
            if not fields:
                raise ValueError("At least one metadata field is required.")

            title = fields.get("title")
            if title is not None:
                title = str(title).strip()
                if not title or len(title) > 120:
                    raise ValueError("title must contain 1 to 120 characters.")

            icon_name = fields.get("icon_name")
            allowed_icons = {"shopping_bag", "receipt_long", "local_shipping", "gavel"}
            if icon_name is not None and icon_name not in allowed_icons:
                raise ValueError(f"icon_name must be one of {sorted(allowed_icons)}")

            response_style = fields.get("response_style")
            allowed_styles = {"simples", "detalhado", "firme"}
            if response_style is not None and response_style not in allowed_styles:
                raise ValueError(f"response_style must be one of {sorted(allowed_styles)}")

            # Validate the complete patch before mutating the loaded case.
            if title is not None:
                case.title = title
            if icon_name is not None:
                case.icon_name = icon_name
            if response_style is not None:
                case.response_style = response_style
            case.updated_at = _now()
            cases.save(case, cases_path=self._cases_path)
        return case

    async def delete_case(self, case_id: UUID) -> bool:
        # Acquire the retained per-case lock for delete. Do not remove the
        # lock afterward: waiters may already reference it, and replacing it
        # would permit two operations for the same UUID to run concurrently.
        case_key = str(case_id)
        lock = await self._get_case_lock(case_key)
        async with lock:
            return cases.delete(case_key, cases_path=self._cases_path)

    async def get_history(self, case_id: UUID) -> list[ChatMessage]:
        # ISSUE-USR-007: thread cases_path through to `cases.load`.
        case = cases.load(str(case_id), cases_path=self._cases_path)
        return case.chat_history if case is not None else []
```

