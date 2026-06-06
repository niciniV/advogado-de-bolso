"""Skill 'redigir documentos': e-mails, reclamacoes, notificacoes, mensagens.

Implementado como tool que delega a um agente secundario com system prompt
especializado, garantindo tom e formato adequados para cada tipo de documento.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_ai import Agent, RunContext

from advogado_de_bolso.deps import Deps

TipoDocumento = Literal[
    "email_cobranca",
    "reclamacao_procon",
    "mensagem_rede_social",
    "notificacao_extrajudicial",
    "recurso",
]

Tom = Literal["formal", "cordial", "firme"]

_SYSTEM_PROMPTS: dict[str, str] = {
    "email_cobranca": (
        "Voce redige e-mails de cobranca elegantes e firmes. "
        "Tom profissional, paragrafos curtos, deixe claro o que foi solicitado, "
        "o que ja foi tentado e qual o prazo esperado para resolucao. "
        "Use portugues brasileiro formal e acessivel."
    ),
    "reclamacao_procon": (
        "Voce redige reclamacoes para o PROCON/SENACON. "
        "Seja objetivo: descreva o problema, cite o CDC quando relevante, "
        "relate o que ja foi tentado resolver diretamente com a empresa, "
        "e termine com o que o consumidor pede. Use portugues brasileiro formal."
    ),
    "mensagem_rede_social": (
        "Voce redige mensagens curtas para Twitter/X, Instagram ou Facebook "
        "direcionadas a marcas ou perfis publicos. "
        "Seja conciso (limite de caracteres quando o canal exigir), direto, "
        "educado mas firme. Objetivo: resolver o problema e/ou pressionar "
        "publicamente para obter resposta."
    ),
    "notificacao_extrajudicial": (
        "Voce redige notificacoes extrajudiciais. "
        "Linguagem juridica acessivel (sem jargoes excessivos), cite o CDC "
        "e o contrato quando relevante, de um prazo para resposta "
        "(tipicamente 10 a 15 dias uteis) e indique as consequencias "
        "do nao atendimento (PROCON, acao judicial, etc.)."
    ),
    "recurso": (
        "Voce redige recursos administrativos contra empresas "
        "(operadoras, bancos, seguradoras, companhias aereas, etc.). "
        "Linguagem clara, cite o CDC e clausulas contratuais quando relevante, "
        "reproduza os fatos, refuta os argumentos da empresa e solicita "
        "a reversao da decisao."
    ),
}


@lru_cache(maxsize=5)
def _get_drafting_agent(tipo: TipoDocumento) -> Agent:
    """Returns a cached drafting Agent for the given document type."""
    return Agent(
        model=None,
        system_prompt=_SYSTEM_PROMPTS[tipo],
    )


async def redigir_documento(
    ctx: RunContext[Deps],
    tipo: TipoDocumento,
    contexto: str,
    objetivo: str,
    destinatario: str,
    tom: Tom = "formal",
) -> str:
    """Redige um documento pronto para o usuario enviar.

    Use esta ferramenta quando o usuario precisar de um texto pronto
    (e-mail, reclamacao, notificacao, mensagem em rede social, recurso)
    para enviar a uma empresa, ao PROCON ou a outro destinatario.

    Args:
        tipo: Tipo do documento a redigir.
        contexto: Resumo do caso e fatos relevantes.
        objetivo: O que o usuario quer alcancar com o documento.
        destinatario: Para quem o documento sera enviado (empresa, PROCON, etc.).
        tom: Tom desejado - 'formal', 'cordial' ou 'firme'.

    Returns:
        O texto final do documento, pronto para uso.
    """
    user_prompt = (
        f"Destinatario: {destinatario}\n"
        f"Tom: {tom}\n"
        f"Objetivo: {objetivo}\n"
        f"Contexto / Resumo do caso:\n{contexto}\n\n"
        "Redija o documento. Responda APENAS com o texto final, sem comentarios, "
        "sem marcacoes tipo 'Aqui esta o documento:', sem aspas em volta. "
        "Voce pode incluir placeholders como [NOME COMPLETO] ou [ENDERECO] "
        "apenas para dados que o usuario tera que preencher."
    )

    drafting_agent = _get_drafting_agent(tipo)
    result = await drafting_agent.run(
        user_prompt,
        model=ctx.model,
        model_settings=ctx.deps.model_settings,
    )
    return result.output
