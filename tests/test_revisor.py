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
