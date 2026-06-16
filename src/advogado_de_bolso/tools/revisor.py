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
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext

from advogado_de_bolso.deps import Deps

REVISION_SYSTEM_PROMPT = """Voce e um revisor especializado em respostas de um
assistente de direitos do consumidor brasileiro (Advogado de Bolso).

Revise a resposta gerada. Seu trabalho e BLOQUEAR APENAS respostas que
causariam dano real ao usuario. Quando estiver em duvida, APROVE.

Bloqueie a resposta (`needs_revision = true`) APENAS se ela contiver um
destes defeitos graves:

1. ERRO JURIDICO FACTUAL: artigo do CDC inexistente, prazo numerico
   incorreto (diferente do que a ferramenta `calcular_prazo_consumidor`
   retornou, se ela foi usada), ou informacao contradita pela base de
   conhecimento consultada nesta conversa.

2. PROMESSA IRREAL: "voce vai ganhar", "com certeza tera direito a X",
   "o processo e garantia de Y", ou qualquer certeza juridica absoluta.

3. FONTE AUSENTE EM AFIRMACAO ESPECIFICA: numero, data, percentual ou
   valor monetario especifico apresentado como fato sem citacao da base
   de conhecimento nem da ferramenta `calcular_prazo_consumidor`.
   NAO bloqueie por "falta de fonte" se a resposta:
   - Explica um artigo do CDC de forma educacional, OU
   - Cita o numero de um artigo do CDC (art. 26, art. 49, etc.) em
     linguagem acessivel, OU
   - Diz honestamente que a base nao tem cobertura (isso e o caminho
     correto, nao uma falta).

4. TOM PERIGOSO: instrucao para falsificar documentos, para agredir o
   fornecedor, ou confianca absoluta que levaria o usuario a abrir mao
   de um direito seu por acreditar em uma garantia sem base.

5. DISCLAIMER: a resposta sera bloqueada por disclaimer ausente apenas
   se ela RECOMENDAR ACAO CONCRETA (entrar com acao judicial, ajuizar
   reclamacao, assinar contrato juridico, mover processo) e nao contiver
   a frase exata da ressalva padrao:
   "nao substituo um advogado inscrito na OAB. Em caso de duvida, procure
   o PROCON, a Defensoria Publica ou consumidor.gov.br."
   Respostas que APENAS INFORMAM um direito, prazo ou artigo do CDC NAO
   precisam de disclaimer; a propria pergunta do usuario e a indicacao de
   que ele quer entender, nao agir juridicamente.

Regra padrao: se voce nao consegue apontar um defeito das listas 1-5
acima com precisao, responda `approved_as_is = true`. E melhor aprovar
uma resposta mediana do que bloquear uma resposta util.

Nao invente problemas. Quando apontar problema, sugira a CORRECAO
CONCRETA (reescreva o trecho)."""


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
        default=False,
        description="True se a resposta esta OK e pode ser entregue sem mudancas.",
    )

    @model_validator(mode="after")
    def _validate_consistency(self) -> RevisionResult:
        if self.approved_as_is and (self.needs_revision or self.issues):
            raise ValueError("Uma resposta aprovada nao pode exigir revisao ou conter problemas.")
        return self


@lru_cache(maxsize=1)
def _get_revision_agent() -> Agent[None, RevisionResult]:
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
    rev = await review_response(
        question=pergunta_usuario,
        response=resposta_original,
        model=ctx.model,
        model_settings=ctx.deps.model_settings,
    )

    if rev.approved_as_is and not rev.needs_revision and not rev.issues:
        return "OK - resposta aprovada sem mudancas."

    parts = [f"REVISAO NECESSARIA ({len(rev.issues)} problema(s)):"]
    for issue in rev.issues:
        parts.append(f"  - {issue}")
    if rev.suggestions:
        parts.append("\nSugestoes de correcao:")
        for s in rev.suggestions:
            parts.append(f"  - {s}")
    return "\n".join(parts)


async def review_response(
    *,
    question: str,
    response: str,
    model: Any,
    model_settings: Any,
) -> RevisionResult:
    """Run the independent reviewer and return its structured verdict."""
    user_prompt = (
        f"PERGUNTA DO USUARIO:\n{question}\n\n"
        f"RESPOSTA GERADA PELO AGENTE PRINCIPAL:\n{response}\n\n"
        "Revise a resposta acima."
    )

    revision_agent = _get_revision_agent()
    result = await revision_agent.run(
        user_prompt,
        model=model,
        model_settings=model_settings,
    )
    return result.output
