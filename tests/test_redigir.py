from __future__ import annotations

from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advogado_de_bolso.tools.redigir import TipoDocumento, redigir_documento


@pytest.fixture
def mock_agent():
    from advogado_de_bolso.tools.redigir import _get_drafting_agent

    _get_drafting_agent.cache_clear()
    with patch("advogado_de_bolso.tools.redigir.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock()
        mock_instance.run.return_value.output = "texto gerado pelo agente mockado"
        MockAgent.return_value = mock_instance
        yield MockAgent
        _get_drafting_agent.cache_clear()


class TestRedigirDocumento:
    @pytest.mark.asyncio
    async def test_returns_drafted_text(self, ctx, mock_agent):
        result = await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Cliente com fatura em atraso ha 30 dias.",
            objetivo="Receber o pagamento.",
            destinatario="Cliente",
            tom="formal",
        )
        assert result == "texto gerado pelo agente mockado"

    @pytest.mark.asyncio
    async def test_agent_created_with_correct_system_prompt(self, ctx, mock_agent):
        await redigir_documento(
            ctx=ctx,
            tipo="reclamacao_procon",
            contexto="Produto com defeito.",
            objetivo="Troca do produto.",
            destinatario="PROCON",
            tom="firme",
        )
        call_kwargs = mock_agent.call_args[1]
        assert "PROCON" in call_kwargs["system_prompt"]

    @pytest.mark.asyncio
    async def test_all_document_types(self, ctx, mock_agent):
        tipos = get_args(TipoDocumento)
        for tipo in tipos:
            result = await redigir_documento(
                ctx=ctx,
                tipo=tipo,
                contexto="Teste",
                objetivo="Teste",
                destinatario="Teste",
                tom="cordial",
            )
            assert result == "texto gerado pelo agente mockado"

    @pytest.mark.asyncio
    async def test_agent_receives_model_settings(self, ctx, mock_agent):
        await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Teste",
            objetivo="Teste",
            destinatario="Teste",
        )
        run_kwargs = mock_agent.return_value.run.call_args[1]
        assert "model_settings" in run_kwargs
        assert run_kwargs["model_settings"] == ctx.deps.model_settings

    @pytest.mark.asyncio
    async def test_tom_appears_in_user_prompt(self, ctx, mock_agent):
        await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Teste",
            objetivo="Teste",
            destinatario="Teste",
            tom="firme",
        )
        user_prompt = mock_agent.return_value.run.call_args[0][0]
        assert "firme" in user_prompt

    @pytest.mark.asyncio
    async def test_invalid_tipo_raises_key_error(self, ctx):
        with pytest.raises(KeyError):
            await redigir_documento(
                ctx=ctx,
                tipo="tipo_inexistente",  # type: ignore[arg-type]
                contexto="Teste",
                objetivo="Teste",
                destinatario="Teste",
            )
