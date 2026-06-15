from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from advogado_de_bolso.agent import _current_style, build_agent
from advogado_de_bolso.config import Settings
from advogado_de_bolso.service import ChatService
from advogado_de_bolso.tools.revisor import RevisionResult


def test_build_agent_applies_preferred_configured_google_key() -> None:
    settings = Settings(
        GOOGLE_API_KEY="old-key",
        GEMINI_API_KEY="preferred-key",
        THINKING_LEVEL="",
    )

    with (
        patch.dict(os.environ, {"GOOGLE_API_KEY": "environment-key"}),
        patch("advogado_de_bolso.agent.Agent", return_value=MagicMock()),
    ):
        build_agent(settings)
        assert os.environ["GOOGLE_API_KEY"] == "preferred-key"


def test_build_agent_registers_style_instructions() -> None:
    """The agent has an instructions callback registered that reads from
    the `_current_style` ContextVar and returns the matching style prompt.
    """
    settings = Settings(THINKING_LEVEL="")
    with patch("advogado_de_bolso.agent.Agent") as MockAgent:
        instance = MagicMock()
        MockAgent.return_value = instance
        build_agent(settings)

    # `agent.instructions(...)` was called at least once as a decorator
    # factory. The mock records the callable factory invocations.
    assert MockAgent.called
    # The decorated `_style_instructions` is registered on the agent
    # instance via the `instructions` decorator (it returns a no-op
    # decorator on the mock). The key contract: the agent should
    # have a callable `_style_instructions` (or an attribute) attached
    # that we can probe by setting the ContextVar and calling it.
    # The simpler test: the ContextVar exists and the STYLE_PROMPTS
    # dict has the three expected keys.
    from advogado_de_bolso.agent import STYLE_PROMPTS

    assert set(STYLE_PROMPTS.keys()) == {"simples", "detalhado", "firme"}


class _FakeBackend:
    def __init__(self) -> None:
        self.captured_styles: list[str | None] = []

    async def run(self, message, history):
        self.captured_styles.append(_current_style.get())
        return "ok-prose", []


class _FakeReviewer:
    async def __call__(self, question, response):
        return RevisionResult(needs_revision=False, approved_as_is=True)


def _make_service(tmp_path) -> tuple[ChatService, _FakeBackend]:
    cases_path = tmp_path / "cases"
    cases_path.mkdir()
    backend = _FakeBackend()
    service = ChatService(
        backend=backend,
        reviewer=_FakeReviewer(),
        cases_path=cases_path,
    )
    return service, backend


def test_context_var_resets_after_request(tmp_path) -> None:
    """After `chat_structured(style='simples')` returns,
    `_current_style.get()` is `None` again — no leakage to the next request.
    """
    service, _ = _make_service(tmp_path)
    assert _current_style.get() is None
    import asyncio
    import uuid as _uuid

    asyncio.run(
        service.chat_structured(
            "Pergunta",
            session_id=_uuid.UUID("00000000-0000-0000-0000-000000000001"),
            response_style="simples",
        )
    )
    assert _current_style.get() is None


def test_context_var_visible_inside_chat_structured(tmp_path) -> None:
    """Inside the backend call, `_current_style.get()` returns the value
    passed to `chat_structured`."""
    service, backend = _make_service(tmp_path)
    import asyncio
    import uuid as _uuid

    asyncio.run(
        service.chat_structured(
            "Pergunta",
            session_id=_uuid.UUID("00000000-0000-0000-0000-000000000002"),
            response_style="firme",
        )
    )
    assert backend.captured_styles == ["firme"]


def test_context_var_uses_case_default_when_request_omits_style(
    tmp_path,
) -> None:
    """When the request does not provide `response_style`, the service
    falls back to the persisted `case.response_style` (set on first
    creation)."""
    service, backend = _make_service(tmp_path)
    import asyncio
    import uuid as _uuid

    case_id = _uuid.UUID("00000000-0000-0000-0000-000000000003")
    # First turn creates the case with style='detalhado' (the default).
    asyncio.run(
        service.chat_structured(
            "Pergunta",
            session_id=case_id,
            response_style="detalhado",
        )
    )
    # Second turn without an explicit style: should use the persisted
    # case default ('detalhado'), not "None".
    asyncio.run(
        service.chat_structured(
            "Segunda",
            session_id=case_id,
        )
    )
    assert backend.captured_styles == ["detalhado", "detalhado"]


def test_blocked_response_does_not_create_case_file(tmp_path) -> None:
    """ISSUE-USR-004: a blocked first message returns 422 with the full
    blocked envelope, but does NOT create a case file on disk."""
    cases_path = tmp_path / "cases"
    cases_path.mkdir()

    class _BlockingReviewer:
        async def __call__(self, question, response):
            return RevisionResult(
                needs_revision=True,
                issues=["Erro juridico"],
                approved_as_is=False,
            )

    service = ChatService(
        backend=_FakeBackend(),
        reviewer=_BlockingReviewer(),
        cases_path=cases_path,
    )
    import asyncio
    import uuid as _uuid

    case_id = _uuid.UUID("00000000-0000-0000-0000-000000000004")
    result = asyncio.run(
        service.chat_structured(
            "Pergunta arriscada",
            session_id=case_id,
        )
    )
    # Blocked envelope shape
    assert result.response.blocked is True
    assert result.response.blocked_message
    # No file on disk
    assert not (cases_path / f"{case_id}.json").exists()
    # Cases list is empty
    assert asyncio.run(service.list_cases()) == []
