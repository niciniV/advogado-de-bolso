"""Application service shared by HTTP and other user interfaces."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

from advogado_de_bolso.agent import build_agent
from advogado_de_bolso.config import Settings
from advogado_de_bolso.deps import Deps
from advogado_de_bolso.knowledge.index import KnowledgeIndex
from advogado_de_bolso.tools.revisor import RevisionResult, review_response

REVIEW_BLOCKED_MESSAGE = (
    "Nao foi possivel validar esta resposta com seguranca. "
    "Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica "
    "ou um advogado de confianca."
)
Reviewer = Callable[[str, str], Awaitable[RevisionResult]]


class ChatBackend(Protocol):
    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]: ...


@dataclass(frozen=True)
class ChatReply:
    session_id: str
    response: str


@dataclass
class _Session:
    history: list[ModelMessage] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    generation: int = 0
    active_calls: int = 0


class AgentChatBackend:
    """Adapter that keeps Pydantic AI details out of the transport layer."""

    def __init__(self, agent: Agent[Deps, str], deps: Deps, reviewer: Reviewer) -> None:
        self._agent = agent
        self._deps = deps
        self._reviewer = reviewer

    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]:
        result = await self._agent.run(message, deps=self._deps, message_history=history)
        revision = await self._reviewer(message, result.output)
        if not revision.approved_as_is:
            return REVIEW_BLOCKED_MESSAGE, history
        return result.output, result.all_messages()


class ChatService:
    """Owns bounded, in-memory conversation sessions."""

    def __init__(
        self,
        backend: ChatBackend,
        *,
        max_history_messages: int = 40,
        max_sessions: int = 500,
    ) -> None:
        if max_history_messages < 1 or max_sessions < 1:
            raise ValueError("Session limits must be positive.")
        self._backend = backend
        self._max_history_messages = max_history_messages
        self._max_sessions = max_sessions
        self._sessions: OrderedDict[str, _Session] = OrderedDict()

    async def chat(self, message: str, session_id: str | None = None) -> ChatReply:
        current_session = session_id or uuid4().hex
        session = self._sessions.setdefault(current_session, _Session())
        session.active_calls += 1
        try:
            async with session.lock:
                generation = session.generation
                response, updated_history = await self._backend.run(
                    message, list(session.history)
                )
                if session.generation == generation:
                    session.history = updated_history[-self._max_history_messages :]
                return ChatReply(session_id=current_session, response=response)
        finally:
            session.active_calls -= 1
            self._sessions.move_to_end(current_session)
            self._evict_old_sessions()

    def clear_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session is None:
            return False
        session.generation += 1
        session.history.clear()
        if session.active_calls == 0:
            self._sessions.pop(session_id, None)
        return True

    def session_history(self, session_id: str) -> list[ModelMessage]:
        """Return a copy for diagnostics and tests without exposing mutable state."""
        session = self._sessions.get(session_id)
        return list(session.history) if session else []

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def _evict_old_sessions(self) -> None:
        empty_sessions = [
            session_id
            for session_id, session in self._sessions.items()
            if session.active_calls == 0 and not session.history
        ]
        for session_id in empty_sessions:
            self._sessions.pop(session_id, None)

        for session_id, session in list(self._sessions.items()):
            if len(self._sessions) <= self._max_sessions:
                break
            if session.active_calls == 0:
                self._sessions.pop(session_id, None)


def build_chat_service(settings: Settings) -> ChatService:
    """Build the production runtime lazily when the first chat request arrives."""
    knowledge = KnowledgeIndex(settings)
    knowledge.build_or_load()
    deps = Deps(settings=settings, retriever=knowledge.as_retriever())

    async def reviewer(question: str, response: str) -> RevisionResult:
        return await review_response(
            question=question,
            response=response,
            model=settings.full_model_name,
            model_settings=settings.build_model_settings(),
        )

    return ChatService(backend=AgentChatBackend(build_agent(settings), deps, reviewer))
