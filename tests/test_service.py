from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from advogado_de_bolso.service import (
    REVIEW_BLOCKED_MESSAGE,
    AgentChatBackend,
    ChatService,
)
from advogado_de_bolso.tools.revisor import RevisionResult


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def run(self, message: str, history: list[Any]) -> tuple[str, list[Any]]:
        self.calls.append((message, list(history)))
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        await asyncio.sleep(0.01)
        self.active_calls -= 1
        return f"Resposta: {message}", [*history, f"user:{message}", f"assistant:{message}"]


class FailingBackend:
    async def run(self, message: str, history: list[Any]) -> tuple[str, list[Any]]:
        raise RuntimeError("backend failed")


@pytest.mark.asyncio
async def test_chat_creates_session_and_reuses_history() -> None:
    backend = FakeBackend()
    service = ChatService(backend=backend)

    first = await service.chat("Primeira pergunta")
    second = await service.chat("Segunda pergunta", first.session_id)

    assert first.session_id == second.session_id
    assert backend.calls[0][1] == []
    assert backend.calls[1][1] == ["user:Primeira pergunta", "assistant:Primeira pergunta"]


@pytest.mark.asyncio
async def test_chat_bounds_saved_history() -> None:
    backend = FakeBackend()
    service = ChatService(backend=backend, max_history_messages=3)

    reply = await service.chat("Primeira")
    await service.chat("Segunda", reply.session_id)

    assert service.session_history(reply.session_id) == [
        "assistant:Primeira",
        "user:Segunda",
        "assistant:Segunda",
    ]


@pytest.mark.asyncio
async def test_clear_session_removes_history() -> None:
    service = ChatService(backend=FakeBackend())
    reply = await service.chat("Pergunta")

    assert service.clear_session(reply.session_id) is True
    assert service.clear_session(reply.session_id) is False
    assert service.session_history(reply.session_id) == []


@pytest.mark.asyncio
async def test_same_session_requests_are_serialized() -> None:
    backend = FakeBackend()
    service = ChatService(backend=backend)
    reply = await service.chat("Inicial")

    await asyncio.gather(
        service.chat("A", reply.session_id),
        service.chat("B", reply.session_id),
    )

    assert backend.max_active_calls == 1


@pytest.mark.asyncio
async def test_clear_during_request_prevents_old_history_from_returning() -> None:
    backend = FakeBackend()
    service = ChatService(backend=backend)
    initial = await service.chat("Inicial")

    in_flight = asyncio.create_task(service.chat("Antiga", initial.session_id))
    await asyncio.sleep(0)
    assert service.clear_session(initial.session_id) is True
    await in_flight

    assert service.session_history(initial.session_id) == []


@pytest.mark.asyncio
async def test_clear_during_request_keeps_followup_serialized() -> None:
    backend = FakeBackend()
    service = ChatService(backend=backend)
    initial = await service.chat("Inicial")

    in_flight = asyncio.create_task(service.chat("Antiga", initial.session_id))
    await asyncio.sleep(0)
    service.clear_session(initial.session_id)
    await service.chat("Nova", initial.session_id)
    await in_flight

    assert backend.max_active_calls == 1


@pytest.mark.asyncio
async def test_failed_requests_do_not_leak_empty_sessions() -> None:
    service = ChatService(backend=FailingBackend(), max_sessions=2)

    for index in range(5):
        with pytest.raises(RuntimeError):
            await service.chat("Falha", f"session-{index}")

    assert service.session_count == 0


@pytest.mark.asyncio
async def test_agent_backend_returns_only_approved_response(deps) -> None:
    result = MagicMock(output="Resposta aprovada.")
    result.all_messages.return_value = ["updated-history"]
    agent = MagicMock()
    agent.run = AsyncMock(return_value=result)
    reviewer = AsyncMock(
        return_value=RevisionResult(needs_revision=False, approved_as_is=True)
    )
    backend = AgentChatBackend(agent, deps, reviewer=reviewer)

    response, history = await backend.run("Pergunta", ["old-history"])

    assert response == "Resposta aprovada."
    assert history == ["updated-history"]
    reviewer.assert_awaited_once_with("Pergunta", "Resposta aprovada.")


@pytest.mark.asyncio
async def test_agent_backend_blocks_unapproved_response_and_discards_draft(deps) -> None:
    result = MagicMock(output="Resposta insegura.")
    result.all_messages.return_value = ["unsafe-history"]
    agent = MagicMock()
    agent.run = AsyncMock(return_value=result)
    reviewer = AsyncMock(
        return_value=RevisionResult(
            needs_revision=True,
            issues=["Erro juridico"],
            approved_as_is=False,
        )
    )
    backend = AgentChatBackend(agent, deps, reviewer=reviewer)

    response, history = await backend.run("Pergunta", ["old-history"])

    assert response == REVIEW_BLOCKED_MESSAGE
    assert history == ["old-history"]
