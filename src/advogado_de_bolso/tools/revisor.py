"""Tool de revisao: revisa a resposta final antes de entregar ao usuario.

Expoto ao agente principal como tool `revisar_resposta`. O agente principal
deve chama-lo quando a resposta for longa, envolver orientacao juridica,
ou citar prazos/legislacao.

CONTRATO: o agente principal DEVE passar apenas o contexto original do
usuario (pergunta_usuario) e o texto final da resposta (resposta_original),
SEM incluir seu proprio raciocinio interno, resultados de ferramentas,
ou conclusoes intermediarias. O revisor deve enxergar apenas o que o
usuario enxerga.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from advogado_de_bolso.deps import Deps

REVISION_SYSTEM_PROMPT = """Voce e um revisor especializado em respostas de um
assistente de direitos do consumidor brasileiro (Advogado de Bolso).

Revise a resposta gerada e identifique APENAS problemas relevantes:

1. ERROS JURIDICOS OU FACTUAIS: artigos do CDC inventados, prazos incorretos,
   informacoes contraditas pela base de conhecimento.
2. EXPECTATIVAS IRREAIS: promessas de resultado, certezas juridicas indevidas.
3. FALTA DE FONTE: afirmacoes factuais sem citacao a base de conhecimento.
4. TOM INADEQUADO: confianca excessiva em opiniao juridica, ambiguidade,
   jargoes desnecessarios, falta de empatia.
5. DISCLAIMERS NECESSARIOS: lembrete de que nao substitui um advogado
   (em casos juridicos relevantes), orientacao a Defensoria Publica/PROCON.

Se a resposta estiver boa, responda "approved_as_is = true" com lista vazia.
Nao invente problemas. Seja direto e objetivo.

Quando apontar problema, sugira a CORRECAO CONCRETA (reescreva o trecho)."""


class RevisionRequest(BaseModel):
    """Input contract for revisar_resposta.

    Forces the caller to explicitly separate user context from the
    generated response, making it harder to accidentally pass internal
    reasoning or tool results.
    """

    resposta_original: str = Field(
        description="Texto final da resposta que sera mostrado ao usuario. "
        "NAO inclua raciocinio interno, resultados de ferramentas, ou "
        "conclusoes intermediarias."
    )
    pergunta_usuario: str = Field(
        description="Texto original do usuario (mensagens do historico). "
        "NAO inclua resultados de ferramentas ou raciocinio do agente."
    )


class RevisionResult(BaseModel):
    needs_revision: bool = Field(
        default=False,
        description="Se a resposta precisa de ajustes antes de ser entregue.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Lista objetiva de problemas encontrados.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Sugestoes concretas de correcao (com texto reescrito quando possivel).",
    )
    approved_as_is: bool = Field(
        default=True,
        description="True se a resposta esta OK e pode ser entregue sem mudancas.",
    )


@lru_cache(maxsize=1)
def _get_revision_agent() -> Agent:
    """Returns a cached revision Agent (created once, reused)."""
    return Agent(
        model=None,
        system_prompt=REVISION_SYSTEM_PROMPT,
        output_type=RevisionResult,
    )


async def revisar_resposta(
    ctx: RunContext[Deps],
    resposta_original: str,
    pergunta_usuario: str,
) -> str:
    """Revisa a resposta antes de enviar ao usuario.

    Args:
        resposta_original: Texto final da resposta que sera enviada ao
            usuario (sem raciocinio interno do agente principal).
        pergunta_usuario: Contexto original do usuario (mensagens do
            historico, sem resultados de ferramentas ou raciocinio).

    Returns:
        Resumo da revisao: "OK - aprovada" ou lista de problemas + sugestoes.
    """
    user_prompt = (
        f"PERGUNTA DO USUARIO:\n{pergunta_usuario}\n\n"
        f"RESPOSTA GERADA PELO AGENTE PRINCIPAL:\n{resposta_original}\n\n"
        "Revise a resposta acima."
    )

    revision_agent = _get_revision_agent()
    result = await revision_agent.run(
        user_prompt,
        model=ctx.model,
        model_settings=ctx.deps.model_settings,
    )
    rev = result.output

    if rev.approved_as_is or not rev.needs_revision:
        return "OK - resposta aprovada sem mudancas."

    parts = [f"REVISAO NECESSARIA ({len(rev.issues)} problema(s)):"]
    for issue in rev.issues:
        parts.append(f"  - {issue}")
    if rev.suggestions:
        parts.append("\nSugestoes de correcao:")
        for s in rev.suggestions:
            parts.append(f"  - {s}")
    return "\n".join(parts)
