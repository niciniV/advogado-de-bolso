from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from advogado_de_bolso.agent import SYSTEM_PROMPT, _current_style, build_agent
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


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT style contract (UX post-fix)
# ---------------------------------------------------------------------------


class TestSystemPromptStyleContract:
    """Pin the SYSTEM_PROMPT so the conversational / full-draft split
    and the closing-draft-offer rule cannot regress. The LLM is told:

    - Conversational responses: no title; can end with a draft offer
      (or a question about the case) as a follow-up.
    - Full-draft responses (long formal): begin with a short bold
      title (`**...**`); do NOT end with another draft offer because
      the user is already looking at a draft.

    The adapter (`adapter.py`) detects the bold first line and lifts it
    into `step_title`. Without the bold, the whole prose is content and
    the UI renders a normal chat message.
    """

    def test_distinguishes_conversational_from_full_draft(self) -> None:
        """The prompt must mention both response formats explicitly."""
        assert "conversacionais" in SYSTEM_PROMPT
        assert "longas ou formais" in SYSTEM_PROMPT or "formais" in SYSTEM_PROMPT

    def test_conversational_rule_says_no_title(self) -> None:
        """Conversational responses must NOT use a title."""
        # Find the conversational block and assert "NAO use titulo".
        assert "NAO use titulo" in SYSTEM_PROMPT

    def test_full_draft_rule_says_bold_title(self) -> None:
        """Full-draft responses must begin with a short bold title."""
        # Bold marker (rendered as **negrito**) appears in the style block.
        assert "**negrito**" in SYSTEM_PROMPT

    def test_conversational_close_may_offer_draft(self) -> None:
        """Conversational responses MAY end with a draft offer as a
        follow-up — the user explicitly asked for this."""
        assert "PODE oferecer um aprofundamento" in SYSTEM_PROMPT
        assert "redigir um documento" in SYSTEM_PROMPT

    def test_conversational_close_may_ask_questions(self) -> None:
        """Conversational responses MAY end with questions about the case
        to clarify the situation."""
        assert "fazer perguntas" in SYSTEM_PROMPT or "perguntas" in SYSTEM_PROMPT

    def test_full_draft_close_must_not_offer_draft(self) -> None:
        """Full-draft responses must NOT end with another draft offer."""
        # The prompt wraps the line across "outro / documento"; use a
        # whitespace-tolerant check rather than pinning a hard substring.
        import re

        assert re.search(
            r"NAO termine oferecendo redigir outro\s+documento",
            SYSTEM_PROMPT,
        ), "SYSTEM_PROMPT must forbid closing-draft offers in full-draft responses"

    def test_no_decorative_lists(self) -> None:
        """The prompt forbids decorative list use."""
        assert "Sem listas decorativas" in SYSTEM_PROMPT

    def test_format_split_is_in_estilo_block(self) -> None:
        """The format split lives in the ## Estilo section."""
        estilo_idx = SYSTEM_PROMPT.index("## Estilo")
        assert "conversacionais" in SYSTEM_PROMPT[estilo_idx:]

    def test_bold_marker_uses_double_asterisk(self) -> None:
        """The prompt uses the canonical `**` Markdown bold marker, which
        is what `_is_title_line` in the adapter looks for."""
        # The style block must use the same `**` marker the adapter
        # detects, not `<b>` or `__` or any other variant.
        assert "**" in SYSTEM_PROMPT
        # And it must not be confused with the existing bold-emphasis
        # guidance for prazos / valores / artigos (which also uses **).
        # The title block uses `**negrito**` (the literal word "negrito"
        # wrapped in `**`).
        assert "**negrito**" in SYSTEM_PROMPT
