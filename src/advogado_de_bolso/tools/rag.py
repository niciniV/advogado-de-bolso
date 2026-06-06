"""Tool de RAG: busca trechos relevantes na base de conhecimento."""

from __future__ import annotations

from pydantic_ai import RunContext

from advogado_de_bolso.deps import Deps


async def search_knowledge_base(
    ctx: RunContext[Deps],
    query: str,
    top_k: int | None = None,
) -> str:
    """Busca trechos relevantes na base de conhecimento sobre direito do consumidor.

    Args:
        query: Pergunta ou tema a ser buscado (ex: "prazo para reclamacao de vicio em produto duravel").
        top_k: Quantidade de trechos a retornar. Se omitido, usa o valor padrao de configuracao.

    Retorna os trechos mais relevantes, cada um com a fonte (nome do arquivo).
    Use esta ferramenta sempre que precisar fundamentar uma resposta em legislacao,
    jurisprudencia, cartilhas do PROCON ou qualquer material indexado.
    """
    retriever = ctx.deps.retriever
    k = top_k if top_k is not None else ctx.deps.settings.retrieval_top_k
    if k < 1:
        k = ctx.deps.settings.retrieval_top_k

    nodes = await retriever.aretrieve(query)
    nodes = sorted(nodes, key=lambda n: getattr(n, "score", 0.0) or 0.0, reverse=True)[:k]

    if not nodes:
        return "Nenhum trecho relevante encontrado na base de conhecimento."

    chunks: list[str] = []
    for i, node in enumerate(nodes, 1):
        source = node.metadata.get("file_name") or node.node_id or "fonte desconhecida"
        text = node.get_content().strip()
        chunks.append(f"[{i}] Fonte: {source}\n{text}")

    return "\n\n---\n\n".join(chunks)
