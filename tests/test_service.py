"""Tests for `ChatService` (batch 4).

Covers the new disk-persistent session model, the per-case `asyncio.Lock`
serialization invariant, the reviewer-blocked envelope, the `_current_style`
ContextVar reset, and `model_history` round-trip.

References
----------
- `.opencode/plans/06-service-class.md` — `ChatService` class spec.
- `.opencode/plans/07-service-helpers-and-backend.md` — module-scope helpers.
- `.opencode/plans/15-backend-tests.md` — test spec.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from advogado_de_bolso.contracts import DeadlineResult
from advogado_de_bolso.schemas import CaseSummary
from advogado_de_bolso.service import (
    REVIEW_BLOCKED_MESSAGE,
    AgentChatBackend,
    ChatBackend,
    ChatResult,
    ChatService,
    ReviewerLike,
    _collect_tool_returns,
    _truncate_history_to_turns,
    build_chat_service,
)
from advogado_de_bolso.tools.revisor import RevisionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[ModelMessage]]] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]:
        self.calls.append((message, list(history)))
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)
        await asyncio.sleep(0.01)
        self.active_calls -= 1
        # Emit a user turn + assistant turn to model_history shape.
        new_msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content=message)]),
            ModelResponse(parts=[TextPart(content=f"Resposta: {message}")]),
        ]
        return f"Resposta: {message}", new_msgs


class ApprovedReviewer:
    async def __call__(self, question: str, response: str) -> RevisionResult:
        return RevisionResult(needs_revision=False, approved_as_is=True)


class BlockingReviewer:
    async def __call__(self, question: str, response: str) -> RevisionResult:
        return RevisionResult(
            needs_revision=True,
            issues=["Erro juridico grave"],
            approved_as_is=False,
        )


@pytest.fixture
def cases_path(tmp_path: Path) -> Path:
    p = tmp_path / "cases"
    p.mkdir()
    return p


@pytest.fixture
def service(cases_path: Path) -> tuple[ChatService, FakeBackend]:
    backend = FakeBackend()
    svc = ChatService(
        backend=backend,
        reviewer=ApprovedReviewer(),
        cases_path=cases_path,
    )
    return svc, backend


@pytest.fixture
def blocking_service(cases_path: Path) -> ChatService:
    return ChatService(
        backend=FakeBackend(),
        reviewer=BlockingReviewer(),
        cases_path=cases_path,
    )


# ---------------------------------------------------------------------------
# Constructor / properties
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_creates_directory_on_init(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "cases"
        assert not nested.exists()
        ChatService(
            backend=FakeBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=nested,
        )
        assert nested.is_dir()

    def test_rejects_non_positive_history_turns(self, cases_path: Path) -> None:
        with pytest.raises(ValueError):
            ChatService(
                backend=FakeBackend(),
                reviewer=ApprovedReviewer(),
                cases_path=cases_path,
                max_llm_history_turns=0,
            )


# ---------------------------------------------------------------------------
# chat_structured: new session
# ---------------------------------------------------------------------------


class TestChatStructuredNewSession:
    @pytest.mark.asyncio
    async def test_creates_case_file_on_first_message(
        self, service: ChatService, cases_path: Path
    ) -> None:
        svc, _ = service
        result = await svc.chat_structured("Ola")
        # The service picks a UUID — assert a file appears.
        assert any(cases_path.glob("*.json"))
        assert isinstance(result, ChatResult)
        assert result.session_id
        assert result.response.session_id == result.session_id

    @pytest.mark.asyncio
    async def test_session_id_round_trip_through_uuid(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        result = await svc.chat_structured("Ola", session_id=cid)
        assert result.session_id == str(cid)

    @pytest.mark.asyncio
    async def test_blocked_first_message_does_not_create_file(
        self, blocking_service: ChatService, cases_path: Path
    ) -> None:
        result = await blocking_service.chat_structured("Pergunta arriscada")
        assert result.response.blocked is True
        assert not any(cases_path.glob("*.json"))


# ---------------------------------------------------------------------------
# chat_structured: existing case
# ---------------------------------------------------------------------------


class TestChatStructuredAppends:
    @pytest.mark.asyncio
    async def test_second_message_appends(
        self, service: ChatService
    ) -> None:
        svc, backend = service
        cid = uuid4()
        await svc.chat_structured("Primeira", session_id=cid)
        await svc.chat_structured("Segunda", session_id=cid)

        history = await svc.get_history(cid)
        # Two turns * (user + assistant) = 4 messages
        assert len(history) == 4
        assert history[0].sender == "user"
        assert history[0].text == "Primeira"
        assert history[1].sender == "assistant"
        assert history[1].text == "Resposta: Primeira"
        assert history[2].sender == "user"
        assert history[2].text == "Segunda"
        assert history[3].sender == "assistant"
        assert history[3].text == "Resposta: Segunda"
        # Backend got a non-empty history on the second call (the
        # model_history from the first turn).
        assert len(backend.calls[1][1]) > 0

    @pytest.mark.asyncio
    async def test_existing_case_ignores_title_and_icon_in_chat_request(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured(
            "Ola",
            session_id=cid,
            title="Title A",
            icon_name="gavel",
        )
        # Subsequent request with different title/icon should NOT
        # mutate the persisted metadata.
        await svc.chat_structured(
            "Segunda",
            session_id=cid,
            title="Title B - should be ignored",
            icon_name="shopping_bag",
        )
        case = await svc.get_case(cid)
        assert case is not None
        assert case.title == "Title A"
        assert case.icon_name == "gavel"


# ---------------------------------------------------------------------------
# chat_structured: blocked
# ---------------------------------------------------------------------------


class TestBlockedEnvelope:
    @pytest.mark.asyncio
    async def test_blocked_existing_case_keeps_history(
        self, service: ChatService, blocking_service: ChatService
    ) -> None:
        # First do one approved turn via the approved service.
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("Primeira aprovada", session_id=cid)
        case_before = await svc.get_case(cid)
        assert case_before is not None
        history_before = list(case_before.chat_history)
        model_history_before = list(case_before.model_history)

        # Now do a blocked turn on the same case (via a fresh reviewer).
        result = await blocking_service.chat_structured(
            "Pergunta arriscada", session_id=cid
        )
        assert result.response.blocked is True
        assert result.response.blocked_message == REVIEW_BLOCKED_MESSAGE

        # The blocked envelope returns the EXISTING chat_history (no
        # rejected user/assistant message appended).
        assert result.response.chat_history == history_before
        # The on-disk state is also unchanged: no rejected message in
        # chat_history, no rejected new_messages in model_history.
        case_after = await blocking_service.get_case(cid)
        assert case_after is not None
        assert case_after.chat_history == history_before
        assert case_after.model_history == model_history_before


# ---------------------------------------------------------------------------
# Per-case lock
# ---------------------------------------------------------------------------


class TestPerCaseLock:
    @pytest.mark.asyncio
    async def test_concurrent_chat_structured_serialized(
        self, cases_path: Path
    ) -> None:
        backend = FakeBackend()
        svc = ChatService(
            backend=backend,
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        await asyncio.gather(
            svc.chat_structured("A", session_id=cid),
            svc.chat_structured("B", session_id=cid),
            svc.chat_structured("C", session_id=cid),
        )
        assert backend.max_active_calls == 1

    @pytest.mark.asyncio
    async def test_retained_lock_after_delete(self, cases_path: Path) -> None:
        """After `delete_case`, the per-case lock is retained in the
        service registry so concurrent in-flight operations and future
        requests continue to serialize on the same lock instance.
        """
        svc = ChatService(
            backend=FakeBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        # Create a case (lock is registered).
        await svc.chat_structured("hello", session_id=cid)
        lock_before = await svc._get_case_lock(str(cid))
        # Delete the case; the lock is retained.
        assert await svc.delete_case(cid) is True
        lock_after = await svc._get_case_lock(str(cid))
        assert lock_before is lock_after
        # Recreate a case with the same id; same lock is reused.
        await svc.chat_structured("hello again", session_id=cid)
        lock_recreate = await svc._get_case_lock(str(cid))
        assert lock_recreate is lock_before

    @pytest.mark.asyncio
    async def test_concurrent_delete_and_chat_use_same_lock(
        self, cases_path: Path
    ) -> None:
        """A delete queued behind an in-flight chat_structured must share
        the same lock instance, so the operations serialize. After
        delete, the lock is still in the registry.
        """
        backend = FakeBackend()
        svc = ChatService(
            backend=backend,
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()

        chat_started = asyncio.Event()
        chat_can_finish = asyncio.Event()

        class _GatedBackend:
            async def run(
                self, message: str, history: list[ModelMessage]
            ) -> tuple[str, list[ModelMessage]]:
                chat_started.set()
                await chat_can_finish.wait()
                return "ok", []

        svc._backend = _GatedBackend()  # type: ignore[assignment]

        chat_task = asyncio.create_task(svc.chat_structured("first", session_id=cid))
        await chat_started.wait()
        delete_task = asyncio.create_task(svc.delete_case(cid))
        await asyncio.sleep(0)
        # Release the chat, then the delete runs; they should serialize.
        chat_can_finish.set()
        await chat_task
        await delete_task
        # The lock is still in the registry (retained).
        assert str(cid) in svc._case_locks


# ---------------------------------------------------------------------------
# ContextVar reset
# ---------------------------------------------------------------------------


class TestContextVarReset:
    @pytest.mark.asyncio
    async def test_context_var_reset_after_request(self, cases_path: Path) -> None:
        from advogado_de_bolso.agent import _current_style

        svc = ChatService(
            backend=FakeBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        await svc.chat_structured("x", session_id=cid, response_style="simples")
        assert _current_style.get() is None


# ---------------------------------------------------------------------------
# update_case_meta
# ---------------------------------------------------------------------------


class TestUpdateCaseMeta:
    @pytest.mark.asyncio
    async def test_updates_title(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        updated = await svc.update_case_meta(cid, title="Novo titulo")
        assert updated.title == "Novo titulo"
        case = await svc.get_case(cid)
        assert case is not None
        assert case.title == "Novo titulo"

    @pytest.mark.asyncio
    async def test_updates_icon_name(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        await svc.update_case_meta(cid, icon_name="shopping_bag")
        case = await svc.get_case(cid)
        assert case is not None
        assert case.icon_name == "shopping_bag"

    @pytest.mark.asyncio
    async def test_updates_response_style(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        await svc.update_case_meta(cid, response_style="simples")
        case = await svc.get_case(cid)
        assert case is not None
        assert case.response_style == "simples"

    @pytest.mark.asyncio
    async def test_missing_case_raises_key_error(self, service: ChatService) -> None:
        svc, _ = service
        with pytest.raises(KeyError):
            await svc.update_case_meta(uuid4(), title="x")

    @pytest.mark.asyncio
    async def test_unknown_field_raises_value_error(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid, bogus_field="x")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_empty_fields_raises_value_error(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid)

    @pytest.mark.asyncio
    async def test_blank_title_raises_value_error(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid, title="   ")

    @pytest.mark.asyncio
    async def test_over_long_title_raises_value_error(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid, title="x" * 121)

    @pytest.mark.asyncio
    async def test_unknown_icon_raises_value_error(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid, icon_name="bogus")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_unknown_style_raises_value_error(
        self, service: ChatService
    ) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        with pytest.raises(ValueError):
            await svc.update_case_meta(cid, response_style="verbose")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# delete_case
# ---------------------------------------------------------------------------


class TestDeleteCase:
    @pytest.mark.asyncio
    async def test_delete_removes_file(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        assert await svc.delete_case(cid) is True
        assert await svc.get_case(cid) is None

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self, service: ChatService) -> None:
        svc, _ = service
        assert await svc.delete_case(uuid4()) is False


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_returns_chat_history(self, service: ChatService) -> None:
        svc, _ = service
        cid = uuid4()
        await svc.chat_structured("hello", session_id=cid)
        history = await svc.get_history(cid)
        assert len(history) == 2
        assert history[0].sender == "user"
        assert history[0].text == "hello"

    @pytest.mark.asyncio
    async def test_missing_case_returns_empty(self, service: ChatService) -> None:
        svc, _ = service
        assert await svc.get_history(uuid4()) == []


# ---------------------------------------------------------------------------
# list_cases
# ---------------------------------------------------------------------------


class TestListCases:
    @pytest.mark.asyncio
    async def test_lists_all_cases(self, service: ChatService) -> None:
        svc, _ = service
        cid1 = uuid4()
        cid2 = uuid4()
        await svc.chat_structured("hello", session_id=cid1, title="Case 1")
        await svc.chat_structured("hello", session_id=cid2, title="Case 2")
        items = await svc.list_cases()
        assert len(items) == 2
        assert {c.id for c in items} == {cid1, cid2}
        for item in items:
            assert isinstance(item, CaseSummary)

    @pytest.mark.asyncio
    async def test_empty_when_no_cases(self, service: ChatService) -> None:
        svc, _ = service
        assert await svc.list_cases() == []


# ---------------------------------------------------------------------------
# model_history persistence
# ---------------------------------------------------------------------------


class TestModelHistory:
    @pytest.mark.asyncio
    async def test_model_history_persists_with_tool_parts(
        self, cases_path: Path
    ) -> None:
        deadline = DeadlineResult(
            tipo_prazo="arrependimento",
            data_inicio="2025-06-01",
            data_limite="2025-06-08",
            dias=7,
            base_legal="CDC art. 49",
            item_label=None,
            vicio_oculto=False,
            nota="nota",
        )

        class _ToolBackend:
            async def run(
                self, message: str, history: list[ModelMessage]
            ) -> tuple[str, list[ModelMessage]]:
                return (
                    "Resposta com prazo.",
                    [
                        ModelRequest(parts=[UserPromptPart(content=message)]),
                        ModelResponse(
                            parts=[
                                ToolCallPart(
                                    tool_name="calcular_prazo_consumidor",
                                    args={"tipo_prazo": "arrependimento"},
                                )
                            ]
                        ),
                        ModelRequest(
                            parts=[
                                ToolReturnPart(
                                    tool_name="calcular_prazo_consumidor",
                                    content=deadline,
                                    tool_call_id="call_1",
                                )
                            ]
                        ),
                        ModelResponse(parts=[TextPart(content="Resposta com prazo.")]),
                    ],
                )

        svc = ChatService(
            backend=_ToolBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        await svc.chat_structured("Posso cancelar?", session_id=cid)

        case = await svc.get_case(cid)
        assert case is not None
        assert len(case.model_history) == 4
        assert isinstance(case.model_history[0], ModelRequest)
        assert isinstance(case.model_history[1], ModelResponse)
        assert isinstance(case.model_history[2], ModelRequest)
        assert isinstance(case.model_history[3], ModelResponse)

    @pytest.mark.asyncio
    async def test_model_history_json_round_trip_dict_content(
        self, cases_path: Path
    ) -> None:
        """ISSUE-USR-016: after a JSON round-trip, the `ToolReturnPart`
        structure is preserved (via the `kind` discriminator), but the
        `content` becomes a plain `dict` — not the typed `DeadlineResult`.
        """
        deadline = DeadlineResult(
            tipo_prazo="arrependimento",
            data_inicio="2025-06-01",
            data_limite="2025-06-08",
            dias=7,
            base_legal="CDC art. 49",
            item_label=None,
            vicio_oculto=False,
            nota="nota",
        )

        class _ToolBackend:
            async def run(
                self, message: str, history: list[ModelMessage]
            ) -> tuple[str, list[ModelMessage]]:
                return (
                    "ok",
                    [
                        ModelRequest(parts=[UserPromptPart(content=message)]),
                        ModelResponse(
                            parts=[
                                ToolCallPart(
                                    tool_name="calcular_prazo_consumidor",
                                    args={},
                                )
                            ]
                        ),
                        ModelRequest(
                            parts=[
                                ToolReturnPart(
                                    tool_name="calcular_prazo_consumidor",
                                    content=deadline,
                                    tool_call_id="call_1",
                                )
                            ]
                        ),
                    ],
                )

        svc = ChatService(
            backend=_ToolBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        await svc.chat_structured("x", session_id=cid)

        # Reload via a fresh service to force JSON round-trip.
        fresh = ChatService(
            backend=FakeBackend(),
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        case = await fresh.get_case(cid)
        assert case is not None
        # The last part of the second ModelRequest is the ToolReturnPart.
        tr_part = None
        for msg in case.model_history:
            if isinstance(msg, ModelRequest):
                for p in msg.parts:
                    if isinstance(p, ToolReturnPart):
                        tr_part = p
        assert tr_part is not None
        # Content is a dict after the round-trip.
        assert isinstance(tr_part.content, dict)
        # The original field values survive.
        assert tr_part.content["dias"] == 7
        assert tr_part.content["base_legal"] == "CDC art. 49"
        assert tr_part.content["tipo_prazo"] == "arrependimento"

    @pytest.mark.asyncio
    async def test_subsequent_turn_sees_persisted_model_history(
        self, cases_path: Path
    ) -> None:
        """A subsequent chat_structured on the same case passes the
        persisted model_history (current turn's new_messages appended to
        the prior model_history) to the backend as the history argument.
        """

        class _CapturingBackend:
            def __init__(self) -> None:
                self.history_by_call: list[list[ModelMessage]] = []

            async def run(
                self, message: str, history: list[ModelMessage]
            ) -> tuple[str, list[ModelMessage]]:
                self.history_by_call.append(list(history))
                return (
                    f"r:{message}",
                    [ModelResponse(parts=[TextPart(content=f"r:{message}")])],
                )

        backend = _CapturingBackend()
        svc = ChatService(
            backend=backend,
            reviewer=ApprovedReviewer(),
            cases_path=cases_path,
        )
        cid = uuid4()
        await svc.chat_structured("first", session_id=cid)
        await svc.chat_structured("second", session_id=cid)
        # The second call's history contains the first call's
        # new_messages (a ModelResponse with the assistant text).
        second_history = backend.history_by_call[1]
        assert len(second_history) >= 1
        # It is a ModelResponse (text part).
        assert isinstance(second_history[0], ModelResponse)


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestCollectToolReturns:
    def test_collects_tool_return_parts(self) -> None:
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="x")]),
            ModelResponse(parts=[TextPart(content="r")]),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="t1",
                        content={"k": "v"},
                        tool_call_id="c1",
                    )
                ]
            ),
        ]
        out = _collect_tool_returns(msgs)
        assert len(out) == 1
        assert out[0].tool_name == "t1"

    def test_empty_list_when_no_returns(self) -> None:
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="x")]),
            ModelResponse(parts=[TextPart(content="r")]),
        ]
        assert _collect_tool_returns(msgs) == []


class TestTruncateHistoryToTurns:
    def test_empty_returns_empty(self) -> None:
        assert _truncate_history_to_turns([], 5) == []

    def test_max_turns_zero_returns_empty(self) -> None:
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="x")]),
        ]
        assert _truncate_history_to_turns(msgs, 0) == []

    def test_keeps_last_n_turns(self) -> None:
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="u1")]),
            ModelResponse(parts=[TextPart(content="a1")]),
            ModelRequest(parts=[UserPromptPart(content="u2")]),
            ModelResponse(parts=[TextPart(content="a2")]),
            ModelRequest(parts=[UserPromptPart(content="u3")]),
            ModelResponse(parts=[TextPart(content="a3")]),
        ]
        out = _truncate_history_to_turns(msgs, 2)
        # Last 2 turns = u2/a2 + u3/a3
        assert len(out) == 4
        assert isinstance(out[0], ModelRequest)
        assert out[0].parts[0].content == "u2"
        assert isinstance(out[1], ModelResponse)
        assert isinstance(out[2], ModelRequest)
        assert out[2].parts[0].content == "u3"

    def test_keeps_tool_call_return_paired(self) -> None:
        """A turn that contains a tool call/return must not be split
        across the truncation boundary."""
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="u1")]),
            ModelResponse(parts=[TextPart(content="a1")]),
            ModelRequest(parts=[UserPromptPart(content="u2")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args={})]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="t",
                        content={"k": "v"},
                        tool_call_id="c1",
                    )
                ]
            ),
            ModelRequest(parts=[UserPromptPart(content="u3")]),
        ]
        # Truncate to 1 turn -> only u3 turn.
        out = _truncate_history_to_turns(msgs, 1)
        assert len(out) == 1
        assert out[0].parts[0].content == "u3"
        # Truncate to 2 turns -> u2 turn (with tool call/return) + u3.
        out = _truncate_history_to_turns(msgs, 2)
        assert len(out) == 4


# ---------------------------------------------------------------------------
# AgentChatBackend (no reviewer)
# ---------------------------------------------------------------------------


class TestAgentChatBackend:
    @pytest.mark.asyncio
    async def test_returns_prose_and_new_messages(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from advogado_de_bolso.deps import Deps

        deps = Deps(settings=Settings_test(), retriever=MagicMock())
        agent = MagicMock()
        result = MagicMock()
        result.output = "Hello"
        result.new_messages.return_value = ["msg1"]
        agent.run = AsyncMock(return_value=result)

        factory = MagicMock(return_value=deps)
        backend = AgentChatBackend(agent, factory)
        prose, msgs = await backend.run("question", [])
        assert prose == "Hello"
        assert msgs == ["msg1"]
        factory.assert_called_once()


def Settings_test() -> Any:  # noqa: N802
    from advogado_de_bolso.config import Settings

    return Settings(THINKING_LEVEL="")


# ---------------------------------------------------------------------------
# build_chat_service wiring
# ---------------------------------------------------------------------------


class TestBuildChatServiceWiring:
    @pytest.mark.asyncio
    async def test_build_chat_service_passes_cases_path(
        self, monkeypatch, cases_path: Path, tmp_path: Path
    ) -> None:
        """The production factory must inject `settings.cases_path` into
        the ChatService (ISSUE-USR-007). We monkey-patch the heavy
        `KnowledgeIndex` + `build_agent` to keep this an integration
        test of the factory wiring only.
        """
        from unittest.mock import MagicMock

        from advogado_de_bolso.config import Settings
        from advogado_de_bolso.deps import Deps

        # Fake KnowledgeIndex: avoid real Chroma/LlamaIndex init.
        class _FakeIndex:
            def __init__(self, settings: Settings) -> None:
                pass

            def build_or_load(self) -> None:
                pass

            def as_retriever(self) -> MagicMock:
                return MagicMock()

        # Fake build_agent: return a MagicMock agent.
        def _fake_build_agent(settings: Settings) -> MagicMock:
            m = MagicMock()
            m.run = MagicMock()  # not awaited
            return m

        # Fake review_response: return an approved result.
        async def _fake_review_response(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(needs_revision=False, approved_as_is=True)

        # Imports happen inside `build_chat_service` — patch at the
        # resolved module path (not at `service.KnowledgeIndex`).
        monkeypatch.setattr(
            "advogado_de_bolso.knowledge.index.KnowledgeIndex", _FakeIndex
        )
        monkeypatch.setattr(
            "advogado_de_bolso.agent.build_agent", _fake_build_agent
        )
        monkeypatch.setattr(
            "advogado_de_bolso.tools.revisor.review_response", _fake_review_response
        )

        settings = Settings(
            CASES_PATH=str(cases_path),
            THINKING_LEVEL="",
        )

        def make_deps() -> Any:
            return Deps(settings=settings, retriever=MagicMock())

        svc = build_chat_service(settings, make_deps)

        assert svc._cases_path == cases_path


# ---------------------------------------------------------------------------
# Protocol surface (ChatBackend / ReviewerLike) — instantiation-guard test
# ---------------------------------------------------------------------------


def test_chat_backend_protocol_defines_run() -> None:
    assert hasattr(ChatBackend, "run")


def test_reviewer_like_protocol_defines_call() -> None:
    assert callable(ReviewerLike)


def test_chat_service_init_signature() -> None:
    sig = inspect.signature(ChatService.__init__)
    assert "backend" in sig.parameters
    assert "reviewer" in sig.parameters
    assert "cases_path" in sig.parameters
    assert "max_llm_history_turns" in sig.parameters
