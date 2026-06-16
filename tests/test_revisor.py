from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advogado_de_bolso.tools.revisor import revisar_resposta


@pytest.fixture
def mock_revision_agent():
    from advogado_de_bolso.tools.revisor import _get_revision_agent

    _get_revision_agent.cache_clear()
    with patch("advogado_de_bolso.tools.revisor.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock()
        MockAgent.return_value = mock_instance
        yield MockAgent
        _get_revision_agent.cache_clear()


class TestRevisarResposta:
    @pytest.mark.asyncio
    async def test_approved_response(self, ctx, mock_revision_agent, mock_revision_result_approved):
        mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved

        result = await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta juridica correta.",
            pergunta_usuario="Quais meus direitos?",
        )

        assert "aprovada" in result.lower()

    @pytest.mark.asyncio
    async def test_needs_revision_response(
        self, ctx, mock_revision_agent, mock_revision_result_needs_fix
    ):
        mock_revision_agent.return_value.run.return_value.output = mock_revision_result_needs_fix

        result = await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta com problema.",
            pergunta_usuario="Qual prazo?",
        )

        assert "REVISAO NECESSARIA" in result
        assert "Prazo incorreto" in result

    @pytest.mark.asyncio
    async def test_agent_created_with_revision_result_output(
        self, ctx, mock_revision_agent, mock_revision_result_approved
    ):
        mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved

        await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta.",
            pergunta_usuario="Pergunta.",
        )

        call_kwargs = mock_revision_agent.call_args[1]
        assert call_kwargs["output_type"].__name__ == "RevisionResult"

    @pytest.mark.asyncio
    async def test_agent_receives_model_settings(
        self, ctx, mock_revision_agent, mock_revision_result_approved
    ):
        mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved

        await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta.",
            pergunta_usuario="Pergunta.",
        )

        run_kwargs = mock_revision_agent.return_value.run.call_args[1]
        assert "model_settings" in run_kwargs
        assert run_kwargs["model_settings"] == ctx.deps.model_settings

    @pytest.mark.asyncio
    async def test_user_prompt_contains_both_inputs(
        self, ctx, mock_revision_agent, mock_revision_result_approved
    ):
        mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved

        await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta do agente.",
            pergunta_usuario="Pergunta do usuario.",
        )

        user_prompt = mock_revision_agent.return_value.run.call_args[0][0]
        assert "Resposta do agente." in user_prompt
        assert "Pergunta do usuario." in user_prompt

    @pytest.mark.asyncio
    async def test_multi_issue_format(self, ctx, mock_revision_agent):
        from advogado_de_bolso.tools.revisor import RevisionResult

        multi_issue = RevisionResult(
            needs_revision=True,
            issues=["Erro A", "Erro B"],
            suggestions=["Corrigir A"],
            approved_as_is=False,
        )
        mock_revision_agent.return_value.run.return_value.output = multi_issue

        result = await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta com problemas.",
            pergunta_usuario="Pergunta.",
        )

        assert "2 problema" in result
        assert "Erro A" in result
        assert "Erro B" in result
        assert "Corrigir A" in result

    @pytest.mark.asyncio
    async def test_needs_revision_false_no_issues_approved(self, ctx, mock_revision_agent):
        from advogado_de_bolso.tools.revisor import RevisionResult

        edge = RevisionResult(
            needs_revision=False,
            issues=[],
            suggestions=[],
            approved_as_is=False,
        )
        mock_revision_agent.return_value.run.return_value.output = edge

        result = await revisar_resposta(
            ctx=ctx,
            resposta_original="Resposta ok.",
            pergunta_usuario="Pergunta.",
        )

        assert "REVISAO NECESSARIA" in result


# ---------------------------------------------------------------------------
# New reviewer contract (post-issue-fix): narrower criteria + "em duvida,
# aprove" default. These tests pin the prompt content so the new
# contract cannot drift back to the old strict-criteria wording.
# ---------------------------------------------------------------------------


class TestRevisionSystemPrompt:
    """Pin the new `REVISION_SYSTEM_PROMPT` content so the prompt cannot
    regress to the old strict-criteria wording. The user-visible bug was
    caused by the agent's "complexos" disclaimer rule and the reviewer's
    "casos juridicos relevantes" disclaimer rule disagreeing about when
    a disclaimer is required. The new prompt narrows both, with explicit
    DO-NOT-trigger lists.
    """

    def test_prompt_contains_em_duvida_aprove_default(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        assert "Quando estiver em duvida, APROVE" in REVISION_SYSTEM_PROMPT
        assert "approved_as_is = true" in REVISION_SYSTEM_PROMPT

    def test_prompt_narrows_criterion_3_for_art_49(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        # Old wording was "FALTA DE FONTE: afirmacoes factuais sem citacao
        # a base de conhecimento." — that blocked Art. 49 educational
        # responses with no KB hit. New wording must explicitly exclude
        # CDC article explanations from "falta de fonte".
        assert "art. 49" in REVISION_SYSTEM_PROMPT
        assert "NAO bloqueie por" in REVISION_SYSTEM_PROMPT

    def test_prompt_narrows_criterion_5_to_concrete_actions(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        # Old wording was "DISCLAIMERS NECESSARIOS: lembrete de que nao
        # substitui um advogado (em casos juridicos relevantes)". The new
        # prompt only requires the disclaimer when the response
        # RECOMMENDS concrete legal action — informational responses
        # about a right or prazo don't need it.
        assert "RECOMENDAR ACAO CONCRETA" in REVISION_SYSTEM_PROMPT
        assert "APENAS INFORMAM" in REVISION_SYSTEM_PROMPT

    def test_prompt_includes_canonical_disclaimer_phrase(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        # The exact phrase the service layer injects MUST appear in the
        # prompt so the reviewer recognizes it as satisfying criterion #5.
        assert "nao substituo um advogado inscrito na OAB" in REVISION_SYSTEM_PROMPT
        assert "PROCON" in REVISION_SYSTEM_PROMPT
        assert "Defensoria Publica" in REVISION_SYSTEM_PROMPT
        assert "consumidor.gov.br" in REVISION_SYSTEM_PROMPT

    def test_prompt_rejects_legal_errors(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        # Criterion #1 (factual legal error) is preserved.
        assert "ERRO JURIDICO FACTUAL" in REVISION_SYSTEM_PROMPT
        assert "artigo do CDC inexistente" in REVISION_SYSTEM_PROMPT

    def test_prompt_rejects_unrealistic_promises(self) -> None:
        from advogado_de_bolso.tools.revisor import REVISION_SYSTEM_PROMPT

        # Criterion #2 (unrealistic promises) is preserved.
        assert "PROMESSA IRREAL" in REVISION_SYSTEM_PROMPT
        assert "voce vai ganhar" in REVISION_SYSTEM_PROMPT


class TestBuildReviewerModelSettings:
    """Pin the new `Settings.build_reviewer_model_settings()` method:
    always MINIMAL, regardless of the main agent's `THINKING_LEVEL`.
    Higher thinking levels for the reviewer expanded the surface area
    for "found a reason to block", which produced intermittent false
    positives on Art. 49 / Art. 26 responses.

    Note: `GoogleModelSettings` is a TypedDict in pydantic-ai>=1.106, so
    `Settings.build_model_settings()` returns a plain `dict`, not an
    attribute-bearing object. Assertions use dict access.
    """

    def test_reviewer_uses_minimal_when_main_uses_high(self) -> None:
        from advogado_de_bolso.config import Settings

        s = Settings(
            GOOGLE_API_KEY="k",
            LLM_PROVIDER="google",
            LLM_MODEL="gemma-4-31b-it",
            THINKING_LEVEL="HIGH",
        )
        assert s.thinking_level == "HIGH"
        main_settings = s.build_model_settings()
        assert main_settings == {"google_thinking_config": {"thinking_level": "HIGH"}}

        reviewer_settings = s.build_reviewer_model_settings()
        assert reviewer_settings == {
            "google_thinking_config": {"thinking_level": "MINIMAL"}
        }

    def test_reviewer_uses_minimal_even_when_main_thinking_disabled(self) -> None:
        from advogado_de_bolso.config import Settings

        s = Settings(
            GOOGLE_API_KEY="k",
            LLM_PROVIDER="google",
            LLM_MODEL="gemma-4-31b-it",
            THINKING_LEVEL="",
        )
        # Main agent: thinking disabled, so build_model_settings() is None.
        assert s.build_model_settings() is None
        # Reviewer: still gets an explicit MINIMAL setting.
        reviewer_settings = s.build_reviewer_model_settings()
        assert reviewer_settings == {
            "google_thinking_config": {"thinking_level": "MINIMAL"}
        }

    def test_reviewer_returns_none_for_non_google_provider(self) -> None:
        from advogado_de_bolso.config import Settings

        s = Settings(
            GOOGLE_API_KEY="k",
            LLM_PROVIDER="openai",
            LLM_MODEL="gpt-4o",
            THINKING_LEVEL="HIGH",
        )
        assert s.build_reviewer_model_settings() is None


class TestBuildChatServiceReviewerSettings:
    """`build_chat_service` must wire the reviewer with
    `build_reviewer_model_settings()` (MINIMAL), not
    `build_model_settings()` (HIGH).
    """

    def test_reviewer_uses_minimal_model_settings(self, monkeypatch) -> None:
        """End-to-end: build the service with `THINKING_LEVEL=HIGH`, then
        drive `chat_structured` against a fake backend. The fake
        `review_response` captures the kwargs the closure passes; we
        assert the captured settings are MINIMAL.
        """
        from unittest.mock import MagicMock

        from advogado_de_bolso.config import Settings
        from advogado_de_bolso.deps import Deps
        from advogado_de_bolso.service import build_chat_service

        class _FakeIndex:
            def __init__(self, settings: Settings) -> None:
                pass

            def build_or_load(self) -> None:
                pass

            def as_retriever(self) -> MagicMock:
                return MagicMock()

        def _fake_build_agent(settings: Settings) -> MagicMock:
            m = MagicMock()
            m.run = MagicMock()
            return m

        captured: dict = {}

        async def _fake_review_response(**kwargs):
            captured["model"] = kwargs.get("model")
            captured["model_settings"] = kwargs.get("model_settings")
            from advogado_de_bolso.tools.revisor import RevisionResult

            return RevisionResult(needs_revision=False, approved_as_is=True)

        monkeypatch.setattr(
            "advogado_de_bolso.knowledge.index.KnowledgeIndex", _FakeIndex
        )
        monkeypatch.setattr(
            "advogado_de_bolso.agent.build_agent", _fake_build_agent
        )
        monkeypatch.setattr(
            "advogado_de_bolso.tools.revisor.review_response",
            _fake_review_response,
        )

        settings = Settings(
            CASES_PATH="./storage/cases-test-reviewer",
            THINKING_LEVEL="HIGH",
        )

        def make_deps() -> Deps:
            return Deps(settings=settings, retriever=MagicMock())

        svc = build_chat_service(settings, make_deps)

        # Sanity: main agent settings are HIGH.
        assert settings.build_model_settings() == {
            "google_thinking_config": {"thinking_level": "HIGH"}
        }

        # Drive a real chat_structured call so the reviewer closure runs
        # and the fake `review_response` captures the kwargs.
        import asyncio

        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        class _Backend:
            async def run(self, message, history):
                return (
                    "Voce tem 7 dias (CDC art. 49).",
                    [
                        ModelRequest(parts=[UserPromptPart(content=message)]),
                        ModelResponse(
                            parts=[TextPart(content="Voce tem 7 dias (CDC art. 49).")]
                        ),
                    ],
                )

        svc._backend = _Backend()  # type: ignore[attr-defined]
        asyncio.run(svc.chat_structured("Posso cancelar?"))

        # After a real call, the captured settings are MINIMAL (the new
        # contract), NOT HIGH (the old one). The reviewer no longer
        # inherits the main agent's THINKING_LEVEL.
        assert captured["model"] == settings.full_model_name
        assert captured["model_settings"] == {
            "google_thinking_config": {"thinking_level": "MINIMAL"}
        }
