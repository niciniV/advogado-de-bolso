"""Tests for the CLI (batch 5).

Covers the reviewer-gated buffered streaming behavior, `/limpar` slash
command, two-turn UUID reuse, blocked envelope, and disk persistence.

Testing strategy
----------------
The CLI is hard to unit-test in isolation because `rich` Live/Spinner
rendering couples the turn flow to the console. To make the behavior
testable, the CLI module exposes a small async helper

    _process_turn(agent, user_input, case, settings, reviewer_fn, deps) -> TurnResult

that:
  1. streams the agent's response into an internal accumulator (no
     console writes — the CLI loop wraps this call with `console.status`),
  2. calls the reviewer with the accumulated prose plus the model name
     and model settings,
  3. returns a `TurnResult` describing what the UI should display and
     what the loop should persist.

The CLI's main loop calls `_process_turn` and handles Rich rendering
plus disk persistence (`cases.save(case, cases_path=settings.cases_path)`).
The tests below exercise `_process_turn` directly with a fake agent
whose `run_stream` is a synchronous context manager yielding chunks, and
a mock `reviewer_fn` that captures keyword arguments. The persistence
pattern and `/limpar` behavior are tested end-to-end by simulating the
loop's state transitions (apply result, save to disk, replace case).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from advogado_de_bolso.cli import (
    REVIEW_BLOCKED_MESSAGE,
    TurnResult,
    _new_cli_case,
    _process_turn,
)
from advogado_de_bolso.config import Settings
from advogado_de_bolso.deps import Deps
from advogado_de_bolso.storage import cases
from advogado_de_bolso.storage.cases import Case
from advogado_de_bolso.tools.revisor import RevisionResult

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeStreamResult:
    """Mimics the object yielded by `agent.run_stream().__aenter__()`."""

    def __init__(
        self,
        chunks: list[str],
        new_messages: list[ModelMessage],
    ) -> None:
        self._chunks = chunks
        self._new_messages = new_messages

    async def stream_text(self, delta: bool = True) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk

    def new_messages(self) -> list[ModelMessage]:
        return list(self._new_messages)


class _StreamCM:
    """Async context manager that yields a `FakeStreamResult`."""

    def __init__(self, result: FakeStreamResult) -> None:
        self._result = result

    async def __aenter__(self) -> FakeStreamResult:
        return self._result

    async def __aexit__(self, *args: Any) -> None:
        return None


class FakeAgent:
    """Mock Pydantic AI Agent. `run_stream` returns a context manager."""

    def __init__(
        self,
        chunks: list[str],
        new_messages: list[ModelMessage] | None = None,
    ) -> None:
        self._chunks = chunks
        self._new_messages = new_messages or []
        self.calls: list[dict[str, Any]] = []

    def run_stream(
        self,
        user_input: str,
        *,
        deps: Any,
        message_history: list[ModelMessage] | None = None,
    ) -> _StreamCM:
        self.calls.append(
            {
                "user_input": user_input,
                "deps": deps,
                "message_history": list(message_history or []),
            }
        )
        return _StreamCM(FakeStreamResult(self._chunks, self._new_messages))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def settings() -> Settings:
    return Settings(THINKING_LEVEL="")


@pytest.fixture
def cli_case() -> Case:
    """A fresh CLI case with the standard CLI defaults."""
    return _new_cli_case()


@pytest.fixture
def mock_deps(settings: Settings) -> Deps:
    """A `Deps` instance with a no-op retriever."""
    from unittest.mock import MagicMock

    return Deps(settings=settings, retriever=MagicMock())


# ---------------------------------------------------------------------------
# _process_turn: approved response
# ---------------------------------------------------------------------------


class TestProcessTurnApproved:
    @pytest.mark.asyncio
    async def test_accumulates_streamed_tokens(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["Resposta", " aprovada"])

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        result = await _process_turn(
            agent, "pergunta", cli_case, settings, reviewer_fn, mock_deps
        )

        assert result.displayed_prose == "Resposta aprovada"
        assert result.blocked is False
        assert result.block_message is None

    @pytest.mark.asyncio
    async def test_reviewer_called_with_question_and_response(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["Resposta", " teste"])
        captured: dict[str, Any] = {}

        async def reviewer_fn(**kwargs: Any) -> RevisionResult:
            captured.update(kwargs)
            return RevisionResult(approved_as_is=True)

        await _process_turn(
            agent, "pergunta do usuario", cli_case, settings, reviewer_fn, mock_deps
        )

        assert captured["question"] == "pergunta do usuario"
        assert captured["response"] == "Resposta teste"

    @pytest.mark.asyncio
    async def test_reviewer_called_with_full_model_name_and_model_settings(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["ok"])
        captured: dict[str, Any] = {}

        async def reviewer_fn(**kwargs: Any) -> RevisionResult:
            captured.update(kwargs)
            return RevisionResult(approved_as_is=True)

        await _process_turn(
            agent, "x", cli_case, settings, reviewer_fn, mock_deps
        )

        assert captured["model"] == settings.full_model_name
        assert captured["model_settings"] == settings.build_model_settings()

    @pytest.mark.asyncio
    async def test_returns_user_and_assistant_chat_messages(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["Resposta"])

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        result = await _process_turn(
            agent, "pergunta", cli_case, settings, reviewer_fn, mock_deps
        )

        assert result.new_chat_messages is not None
        user_msg, assistant_msg = result.new_chat_messages
        assert user_msg.sender == "user"
        assert user_msg.text == "pergunta"
        assert assistant_msg.sender == "assistant"
        assert assistant_msg.text == "Resposta"
        # User and assistant timestamps differ (assistant is +1ms).
        assert assistant_msg.timestamp == user_msg.timestamp + 1

    @pytest.mark.asyncio
    async def test_returns_new_messages_for_model_history(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        new_msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="x")]),
            ModelResponse(parts=[TextPart(content="r")]),
        ]
        agent = FakeAgent(chunks=["r"], new_messages=new_msgs)

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        result = await _process_turn(
            agent, "x", cli_case, settings, reviewer_fn, mock_deps
        )

        assert result.new_messages == new_msgs

    @pytest.mark.asyncio
    async def test_passes_model_history_to_agent(
        self, settings: Settings, mock_deps: Deps
    ) -> None:
        prior_msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="prior")]),
            ModelResponse(parts=[TextPart(content="r")]),
        ]
        case = _new_cli_case()
        case.model_history = list(prior_msgs)
        agent = FakeAgent(chunks=["ok"])

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        await _process_turn(
            agent, "next", case, settings, reviewer_fn, mock_deps
        )

        assert agent.calls[0]["message_history"] == prior_msgs

    @pytest.mark.asyncio
    async def test_does_not_mutate_case(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        """`_process_turn` is a pure function — it returns a TurnResult;
        it does NOT mutate the Case in place. The CLI loop applies the
        result and saves to disk.
        """
        new_msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="x")]),
            ModelResponse(parts=[TextPart(content="r")]),
        ]
        agent = FakeAgent(chunks=["r"], new_messages=new_msgs)
        original_chat_history = list(cli_case.chat_history)
        original_model_history = list(cli_case.model_history)
        original_updated_at = cli_case.updated_at

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        await _process_turn(
            agent, "x", cli_case, settings, reviewer_fn, mock_deps
        )

        assert cli_case.chat_history == original_chat_history
        assert cli_case.model_history == original_model_history
        assert cli_case.updated_at == original_updated_at


# ---------------------------------------------------------------------------
# _process_turn: blocked response
# ---------------------------------------------------------------------------


class TestProcessTurnBlocked:
    @pytest.mark.asyncio
    async def test_blocked_returns_review_blocked_message(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["r", " perigoso"])

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(
                needs_revision=True,
                issues=["Erro juridico grave"],
                approved_as_is=False,
            )

        result = await _process_turn(
            agent, "x", cli_case, settings, reviewer_fn, mock_deps
        )

        assert result.blocked is True
        assert result.block_message == REVIEW_BLOCKED_MESSAGE

    @pytest.mark.asyncio
    async def test_blocked_does_not_return_prose_or_new_messages(
        self, settings: Settings, cli_case: Case, mock_deps: Deps
    ) -> None:
        agent = FakeAgent(chunks=["r", " perigoso"])

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=False)

        result = await _process_turn(
            agent, "x", cli_case, settings, reviewer_fn, mock_deps
        )

        # Prose is NOT returned for display.
        assert result.displayed_prose == ""
        assert result.new_chat_messages is None
        assert result.new_messages == []


# ---------------------------------------------------------------------------
# _new_cli_case
# ---------------------------------------------------------------------------


class TestNewCLICase:
    def test_returns_case_with_cli_defaults(self) -> None:
        case = _new_cli_case()
        assert case.title == "Consulta via CLI"
        assert case.icon_name == "gavel"
        assert case.response_style == "detalhado"
        assert case.is_demo is False
        assert case.chat_history == []
        assert case.model_history == []
        # UUID format
        UUID(case.id)
        # created_at and updated_at are equal
        assert case.created_at == case.updated_at

    def test_returns_fresh_uuid_each_call(self) -> None:
        c1 = _new_cli_case()
        c2 = _new_cli_case()
        assert c1.id != c2.id

    def test_created_at_is_close_to_now(self) -> None:
        before = datetime.now(UTC)
        case = _new_cli_case()
        after = datetime.now(UTC)
        assert before <= case.created_at <= after


# ---------------------------------------------------------------------------
# Two-turn UUID reuse (loop pattern)
# ---------------------------------------------------------------------------


class TestTwoTurnUUIDReuse:
    @pytest.mark.asyncio
    async def test_two_approved_turns_reuse_same_case(
        self, settings: Settings, mock_deps: Deps
    ) -> None:
        """The CLI loop passes the same Case object to `_process_turn` for
        every turn. After two approved turns:
          - same UUID is used
          - the original `created_at` is preserved
          - `updated_at` advances
          - both `chat_history` and `model_history` are appended
            (not replaced)
        """
        case = _new_cli_case()
        original_id = case.id
        original_created_at = case.created_at

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        # First turn
        agent1 = FakeAgent(
            chunks=["r1"],
            new_messages=[
                ModelRequest(parts=[UserPromptPart(content="t1")]),
                ModelResponse(parts=[TextPart(content="r1")]),
            ],
        )
        result1 = await _process_turn(
            agent1, "primeira", case, settings, reviewer_fn, mock_deps
        )
        # Apply the result (this is what the CLI loop does).
        assert result1.new_chat_messages is not None
        case.chat_history.extend(result1.new_chat_messages)
        case.model_history = case.model_history + result1.new_messages
        case.updated_at = datetime.now(UTC)

        # Second turn on the same case
        agent2 = FakeAgent(
            chunks=["r2"],
            new_messages=[
                ModelRequest(parts=[UserPromptPart(content="t2")]),
                ModelResponse(parts=[TextPart(content="r2")]),
            ],
        )
        result2 = await _process_turn(
            agent2, "segunda", case, settings, reviewer_fn, mock_deps
        )
        case.chat_history.extend(result2.new_chat_messages or [])
        case.model_history = case.model_history + result2.new_messages
        case.updated_at = datetime.now(UTC)

        # Same UUID, same created_at, advanced updated_at
        assert case.id == original_id
        assert case.created_at == original_created_at
        assert case.updated_at >= original_created_at
        # chat_history has 4 messages (2 turns × 2 messages each)
        assert len(case.chat_history) == 4
        # model_history has 4 messages (2 turns × 2 model messages each)
        assert len(case.model_history) == 4


# ---------------------------------------------------------------------------
# /limpar: fresh case, prior case file preserved
# ---------------------------------------------------------------------------


class TestClearCommandPattern:
    @pytest.mark.asyncio
    async def test_new_case_after_save_preserves_old_file(
        self, settings: Settings, mock_deps: Deps, tmp_path: Path
    ) -> None:
        """Simulates the /limpar flow: an approved turn saves the case to
        disk, then the loop replaces the in-memory case with a fresh
        one. The previous case file MUST remain on disk.
        """
        settings.cases_path = tmp_path
        case = _new_cli_case()
        original_id = case.id

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        agent = FakeAgent(
            chunks=["r"],
            new_messages=[
                ModelRequest(parts=[UserPromptPart(content="x")]),
                ModelResponse(parts=[TextPart(content="r")]),
            ],
        )
        result = await _process_turn(
            agent, "x", case, settings, reviewer_fn, mock_deps
        )
        # Apply and save (the loop does this).
        case.chat_history.extend(result.new_chat_messages or [])
        case.model_history = case.model_history + result.new_messages
        case.updated_at = datetime.now(UTC)
        cases.save(case, cases_path=settings.cases_path)

        # Confirm the file exists.
        old_file = tmp_path / f"{original_id}.json"
        assert old_file.exists()

        # Now simulate /limpar: replace the in-memory case.
        new_case = _new_cli_case()
        assert new_case.id != original_id

        # The old case file is untouched.
        assert old_file.exists()
        # The new case is fresh.
        assert new_case.chat_history == []
        assert new_case.model_history == []
        assert new_case.created_at == new_case.updated_at


# ---------------------------------------------------------------------------
# Disk persistence of approved turn
# ---------------------------------------------------------------------------


class TestDiskPersistence:
    @pytest.mark.asyncio
    async def test_approved_turn_persists_case(
        self, settings: Settings, mock_deps: Deps, tmp_path: Path
    ) -> None:
        """After an approved turn, the loop calls `cases.save(case,
        cases_path=settings.cases_path)` and the file appears on disk
        with the case content.
        """
        settings.cases_path = tmp_path
        case = _new_cli_case()
        cid = case.id

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=True)

        agent = FakeAgent(
            chunks=["Resposta persistida"],
            new_messages=[
                ModelRequest(parts=[UserPromptPart(content="x")]),
                ModelResponse(parts=[TextPart(content="Resposta persistida")]),
            ],
        )
        result = await _process_turn(
            agent, "x", case, settings, reviewer_fn, mock_deps
        )
        case.chat_history.extend(result.new_chat_messages or [])
        case.model_history = case.model_history + result.new_messages
        case.updated_at = datetime.now(UTC)
        cases.save(case, cases_path=settings.cases_path)

        file_path = tmp_path / f"{cid}.json"
        assert file_path.exists()

        # Reload and verify.
        loaded = cases.load(cid, cases_path=tmp_path)
        assert loaded is not None
        assert loaded.id == cid
        assert len(loaded.chat_history) == 2
        assert loaded.chat_history[0].text == "x"
        assert loaded.chat_history[1].text == "Resposta persistida"
        assert len(loaded.model_history) == 2

    @pytest.mark.asyncio
    async def test_blocked_turn_does_not_save_case(
        self, settings: Settings, mock_deps: Deps, tmp_path: Path
    ) -> None:
        """A blocked turn returns a TurnResult with no chat/model history
        to append. The loop does NOT call `cases.save` on a blocked
        turn, so the case file is never created.
        """
        settings.cases_path = tmp_path
        case = _new_cli_case()
        cid = case.id

        async def reviewer_fn(**_kwargs: Any) -> RevisionResult:
            return RevisionResult(approved_as_is=False)

        agent = FakeAgent(chunks=["r perigoso"])
        result = await _process_turn(
            agent, "x", case, settings, reviewer_fn, mock_deps
        )
        # Loop: do NOT apply the result, do NOT save.
        assert result.blocked is True
        # No file should exist (we never called cases.save).
        assert not (tmp_path / f"{cid}.json").exists()


# ---------------------------------------------------------------------------
# REVIEW_BLOCKED_MESSAGE constant
# ---------------------------------------------------------------------------


class TestBlockedMessageConstant:
    def test_blocked_message_is_set(self) -> None:
        from advogado_de_bolso.service import REVIEW_BLOCKED_MESSAGE as SVC_BLOCKED

        # The CLI constant is the same string as the service constant.
        assert REVIEW_BLOCKED_MESSAGE == SVC_BLOCKED
        # Spot-check the user-facing wording.
        assert "PROCON" in REVIEW_BLOCKED_MESSAGE
        assert "Defensoria" in REVIEW_BLOCKED_MESSAGE


# ---------------------------------------------------------------------------
# TurnResult dataclass
# ---------------------------------------------------------------------------


class TestTurnResultDataclass:
    def test_default_values(self) -> None:
        result = TurnResult()
        assert result.displayed_prose == ""
        assert result.block_message is None
        assert result.blocked is False
        assert result.new_messages == []
        assert result.new_chat_messages is None

    def test_blocked_factory_shape(self) -> None:
        result = TurnResult(block_message=REVIEW_BLOCKED_MESSAGE, blocked=True)
        assert result.blocked is True
        assert result.block_message == REVIEW_BLOCKED_MESSAGE
        # No chat history to append on a blocked turn.
        assert result.new_chat_messages is None
        assert result.new_messages == []
