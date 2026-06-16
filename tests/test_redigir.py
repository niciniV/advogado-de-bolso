from __future__ import annotations

from typing import get_args
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from advogado_de_bolso.contracts import DraftedDocument, Tom
from advogado_de_bolso.tools.redigir import TipoDocumento, _split_assunto, redigir_documento
from advogado_de_bolso.tools.redigir import Tom as RedigirTom


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


class TestSplitAssunto:
    """`_split_assunto` lifts a leading 'Assunto: ...' line out of a drafted
    letter and returns the rest as the body. The sub-agent is instructed to
    start the letter with that header line; this helper is what enforces
    the contract on the way out of the tool."""

    def test_lifts_assunto_line(self):
        out = _split_assunto(
            "Assunto: Notificacao de Desistencia\n\nPrezados,\n\nCorpo."
        )
        assert out == {
            "assunto": "Notificacao de Desistencia",
            "texto": "Prezados,\n\nCorpo.",
        }

    def test_lifts_assunto_with_lowercase_prefix(self):
        out = _split_assunto("assunto: foo\n\nCorpo")
        assert out["assunto"] == "foo"
        assert out["texto"] == "Corpo"

    def test_lifts_assunto_with_space_before_colon(self):
        out = _split_assunto("Assunto : foo\n\nCorpo")
        assert out["assunto"] == "foo"
        assert out["texto"] == "Corpo"

    def test_strips_leading_whitespace_before_assunto(self):
        out = _split_assunto("\n\n  Assunto: foo\n\nCorpo")
        assert out["assunto"] == "foo"
        assert out["texto"] == "Corpo"

    def test_empty_string_returns_empty(self):
        assert _split_assunto("") == {"assunto": "", "texto": ""}

    def test_no_assunto_line_returns_full_text_as_body(self):
        out = _split_assunto("Prezados,\n\nCorpo do documento.")
        assert out == {"assunto": "", "texto": "Prezados,\n\nCorpo do documento."}

    def test_assunto_only_no_body(self):
        out = _split_assunto("Assunto: Apenas o assunto")
        assert out["assunto"] == "Apenas o assunto"
        assert out["texto"] == ""


class TestRedigirDocumento:
    @pytest.mark.asyncio
    async def test_returns_drafted_document(self, ctx, mock_agent):
        result = await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Cliente com fatura em atraso ha 30 dias.",
            objetivo="Receber o pagamento.",
            destinatario="Cliente",
            tom="formal",
        )
        assert isinstance(result, DraftedDocument)
        assert result.tipo == "email_cobranca"
        assert result.tom == "formal"
        assert result.destinatario == "Cliente"
        # No 'Assunto:' in the mocked output -> empty subject, full text in body
        assert result.assunto == ""
        assert result.texto == "texto gerado pelo agente mockado"

    @pytest.mark.asyncio
    async def test_extracts_assunto_from_sub_agent_output(self, ctx, mock_agent):
        mock_agent.return_value.run.return_value.output = (
            "Assunto: Notificacao de Desistencia\n\n"
            "Prezados,\n\nSolicito a devolucao..."
        )
        result = await redigir_documento(
            ctx=ctx,
            tipo="notificacao_extrajudicial",
            contexto="Compra de celular realizada online.",
            objetivo="Solicitar a devolucao.",
            destinatario="Loja X",
            tom="formal",
        )
        assert result.assunto == "Notificacao de Desistencia"
        assert result.texto == "Prezados,\n\nSolicito a devolucao..."
        assert "Assunto" not in result.texto

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
    async def test_user_prompt_requires_assunto_header(self, ctx, mock_agent):
        """The sub-agent's user prompt must tell it to start the document
        with an 'Assunto: <subject>' line so the parser can split the
        subject out into a separate wire field."""
        await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Teste",
            objetivo="Teste",
            destinatario="Teste",
        )
        user_prompt = mock_agent.return_value.run.call_args[0][0]
        assert "Assunto:" in user_prompt
        assert "Formato obrigatorio" in user_prompt

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
            assert isinstance(result, DraftedDocument)
            assert result.tipo == tipo
            assert result.tom == "cordial"
            assert result.destinatario == "Teste"
            assert result.texto == "texto gerado pelo agente mockado"

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
    async def test_apenas_instruction_preserved_in_user_prompt(self, ctx, mock_agent):
        """ISSUE-USR-017: the 'Responda APENAS com o texto final' safety
        constraint must remain in the sub-agent's user prompt to prevent the
        sub-agent from emitting JSON envelopes or surrounding commentary
        that would have to be stripped before being placed in
        DraftedDocument.texto."""
        await redigir_documento(
            ctx=ctx,
            tipo="email_cobranca",
            contexto="Teste",
            objetivo="Teste",
            destinatario="Teste",
        )
        user_prompt = mock_agent.return_value.run.call_args[0][0]
        assert "APENAS" in user_prompt

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


class TestTomAlias:
    """ISSUE-USR-017: `Tom` is defined canonically in `contracts.py`.
    `tools/redigir.py` imports and re-exports it for backward compatibility
    with downstream `from .redigir import Tom` imports."""

    def test_tom_re_exported_from_redigir(self):
        assert RedigirTom is Tom

    def test_tom_values_match_canonical(self):
        assert get_args(RedigirTom) == get_args(Tom)
        assert set(get_args(RedigirTom)) == {"formal", "cordial", "firme"}
