"""Application service shared by HTTP and other user interfaces.

`ChatService.chat_structured` is the new primary method (batch 4). It loads
or creates a per-case JSON file (disk is the source of truth), runs the
agent via the injected `ChatBackend`, then runs the reviewer exactly once
per turn. Approved turns are appended to `chat_history` AND the LLM-bound
`model_history` and persisted to disk. Blocked turns are returned with
`blocked=True` and the persisted `chat_history` snapshot — no save.

Per-case `asyncio.Lock` instances are retained in `_case_locks` for the
service lifetime, even after `delete_case`. This prevents the
"old-lock/new-lock" race where a deleted case is recreated with a new
lock while a concurrent in-flight `chat_structured` still holds the old
lock reference.

The agent's response style is propagated to the agent's instructions
callback via the `_current_style` ContextVar (set in `chat_structured`
and reset in `finally`). See `agent.py` for the consumer.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from contextvars import Token
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ToolReturnPart,
    UserPromptPart,
)

from . import schemas
from .adapter import extract_structured_response
from .agent import _current_style
from .config import Settings
from .deps import Deps
from .schemas import CaseSummary, ChatMessage
from .storage import cases
from .storage.cases import Case
from .tools.revisor import RevisionResult

REVIEW_BLOCKED_MESSAGE = (
    "Nao foi possivel validar esta resposta com seguranca. "
    "Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica "
    "ou um advogado de confianca."
)


def _now() -> datetime:
    return datetime.now(UTC)


def _now_ms() -> int:
    """Integer milliseconds since the Unix epoch. Uses `time.time_ns()` to
    avoid the float-multiplication `int(time.time() * 1000)` pattern that
    mypy strict flags."""
    return time.time_ns() // 1_000_000


def _collect_tool_returns(new_messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Walk the current turn's `new_messages` and collect every `ToolReturnPart`.

    Scans both `ModelRequest` and `ModelResponse` parts defensively (the tool
    return is a request-side part for the next turn, but the helper makes
    no assumption about which side carries it). Must be called with
    `result.new_messages()` (current turn only) — never with
    `result.all_messages()`, which would include prior turns' tool returns
    and cause stale `deadline` / `template_letter` / `relevant_chunks` to
    leak into the adapter.
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

    A single turn that triggers a tool call emits 2-4 `ModelMessage`
    objects (one `ModelRequest(parts=[UserPromptPart, ...])`, one
    `ModelResponse(parts=[TextPart, ToolCallPart])`, one or more
    `ModelRequest(parts=[ToolReturnPart])`). Slicing by raw message count
    can cut off a `ToolCallPart` while preserving its matching
    `ToolReturnPart`, producing an invalid provider history. Instead, we
    group messages into turns at every `ModelRequest` that contains a
    `UserPromptPart`, and slice to the last `max_turns` turn groups, so
    every tool call/return pair stays paired.

    `max_turns < 1` returns an empty list (caller has already validated).
    """
    if max_turns < 1:
        return []
    if not history:
        return []

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


@dataclass(frozen=True)
class ChatResult:
    """Wire-result wrapper for `chat_structured`.

    Renamed from `StructuredChatResponse` to avoid the self-naming
    collision with `schemas.StructuredChatResponse` (ISSUE-002). The
    `response` field is a `schemas.StructuredChatResponse`.
    """

    session_id: str
    response: schemas.StructuredChatResponse


class ChatBackend(Protocol):
    """Plain `run(message, history) -> (prose, new_messages)` contract.

    The backend does NOT run the reviewer. The reviewer is called by
    `ChatService` (ISSUE-M3-003). The returned `prose` is the raw agent
    output; the returned `new_messages` is the **current turn's**
    `ModelMessage` list from `result.new_messages()` (excluding the input
    `message_history` and any prior runs).
    """

    async def run(
        self,
        message: str,
        history: list[ModelMessage],
    ) -> tuple[str, list[ModelMessage]]: ...


class ReviewerLike(Protocol):
    async def __call__(self, question: str, response: str) -> RevisionResult: ...


class AgentChatBackend:
    """Implements `ChatBackend`. Does NOT run the reviewer — the service does."""

    def __init__(
        self,
        agent: Agent[Deps, str],
        deps_factory: Callable[[], Deps],
    ) -> None:
        self._agent = agent
        self._deps_factory = deps_factory

    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]:
        deps = self._deps_factory()
        result: AgentRunResult[str] = await self._agent.run(
            message, deps=deps, message_history=history
        )
        prose = result.output
        new_messages = result.new_messages()
        return prose, new_messages


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
        self._cases_path = cases_path
        self._max_llm_history_turns = max_llm_history_turns
        self._case_locks: dict[str, asyncio.Lock] = {}
        self._locks_meta_lock = asyncio.Lock()
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
        icon_name: Literal[
            "shopping_bag", "receipt_long", "local_shipping", "gavel"
        ]
        | None = None,
    ) -> ChatResult:
        case_id = str(session_id) if session_id is not None else str(uuid.uuid4())
        lock = await self._get_case_lock(case_id)
        async with lock:
            case = cases.load(case_id, cases_path=self._cases_path)
            if case is None:
                case = Case(
                    id=case_id,
                    title=title or "Nova consulta",
                    icon_name=icon_name or "gavel",
                    response_style=response_style or "detalhado",
                    is_demo=False,
                    created_at=_now(),
                    updated_at=_now(),
                    chat_history=[],
                    model_history=[],
                )

            effective_style = response_style or case.response_style or "detalhado"
            style_token: Token[str | None] = _current_style.set(effective_style)
            try:
                llm_history = _truncate_history_to_turns(
                    case.model_history, self._max_llm_history_turns
                )

                prose, new_messages = await self._backend.run(message, llm_history)

                revision = await self._reviewer(message, prose)
                blocked = not revision.approved_as_is
                blocked_message = REVIEW_BLOCKED_MESSAGE if blocked else None

                if blocked:
                    structured = extract_structured_response(
                        blocked_message or "",
                        [],
                        blocked=True,
                        blocked_message=blocked_message,
                    )
                    structured.session_id = case_id
                    structured.chat_history = list(case.chat_history)
                    structured.updated_at = case.updated_at
                    return ChatResult(session_id=case_id, response=structured)

                tool_returns = _collect_tool_returns(new_messages)
                structured = extract_structured_response(prose, tool_returns)
                structured.session_id = case_id

                user_ts = _now_ms()
                assistant_ts = user_ts + 1
                case.chat_history.append(
                    ChatMessage(
                        id=f"user-{user_ts}",
                        sender="user",
                        text=message,
                        timestamp=user_ts,
                    )
                )
                case.chat_history.append(
                    ChatMessage(
                        id=f"assistant-{assistant_ts}",
                        sender="assistant",
                        text=prose,
                        timestamp=assistant_ts,
                        step_title=structured.step_title,
                        step_content=structured.step_content,
                        relevant_title=structured.relevant_title,
                        relevant_content=structured.relevant_content,
                        deadline=structured.deadline,
                        questions=structured.questions,
                        suggestive_text=structured.suggestive_text,
                        template_letter=structured.template_letter,
                        quick_replies=structured.quick_replies,
                    )
                )
                case.updated_at = _now()
                case.model_history = case.model_history + new_messages

                structured.chat_history = list(case.chat_history)
                structured.updated_at = case.updated_at

                cases.save(case, cases_path=self._cases_path)
                return ChatResult(session_id=case_id, response=structured)
            finally:
                _current_style.reset(style_token)

    async def list_cases(self) -> list[CaseSummary]:
        return cases.list_all(cases_path=self._cases_path)

    async def get_case(self, case_id: UUID) -> Case | None:
        return cases.load(str(case_id), cases_path=self._cases_path)

    async def update_case_meta(
        self, case_id: UUID, **fields: Any
    ) -> Case:
        """Validates and applies partial metadata updates (`title`,
        `icon_name`, `response_style`). The API layer delegates to this
        method so the per-field validation lives in the service, not the
        endpoint. The PATCH body is the new `UpdateCaseRequest` schema —
        so all three fields can be patched in a single request.
        """
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
            allowed_icons = {
                "shopping_bag",
                "receipt_long",
                "local_shipping",
                "gavel",
            }
            if icon_name is not None and icon_name not in allowed_icons:
                raise ValueError(f"icon_name must be one of {sorted(allowed_icons)}")

            response_style = fields.get("response_style")
            allowed_styles = {"simples", "detalhado", "firme"}
            if response_style is not None and response_style not in allowed_styles:
                raise ValueError(
                    f"response_style must be one of {sorted(allowed_styles)}"
                )

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
        case_key = str(case_id)
        lock = await self._get_case_lock(case_key)
        async with lock:
            return cases.delete(case_key, cases_path=self._cases_path)

    async def get_history(self, case_id: UUID) -> list[ChatMessage]:
        case = cases.load(str(case_id), cases_path=self._cases_path)
        return case.chat_history if case is not None else []


def build_chat_service(
    settings: Settings,
    deps_factory: Callable[[], Deps] | None = None,
) -> ChatService:
    """Build the production runtime. If `deps_factory` is `None`, a default
    one is constructed that builds `Deps` against the production
    `KnowledgeIndex`.

    The lifespan in `api.py` calls this without arguments so the default
    factory path is the production wiring; tests inject a custom
    `deps_factory` to avoid touching Chroma / LlamaIndex at import time.
    """
    from .agent import build_agent
    from .knowledge.index import KnowledgeIndex
    from .tools.revisor import review_response

    knowledge = KnowledgeIndex(settings)
    knowledge.build_or_load()

    if deps_factory is None:
        retriever = knowledge.as_retriever()
        deps_factory = lambda: Deps(  # noqa: E731
            settings=settings, retriever=retriever
        )

    agent = build_agent(settings)

    async def reviewer(question: str, response: str) -> RevisionResult:
        return await review_response(
            question=question,
            response=response,
            model=settings.full_model_name,
            model_settings=settings.build_model_settings(),
        )

    return ChatService(
        backend=AgentChatBackend(agent, deps_factory),
        reviewer=reviewer,
        cases_path=settings.cases_path,
    )
