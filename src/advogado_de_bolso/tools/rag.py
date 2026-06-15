"""Tool de RAG: busca trechos relevantes na base de conhecimento."""

from __future__ import annotations

from pydantic_ai import RunContext

from advogado_de_bolso.contracts import KnowledgeChunk
from advogado_de_bolso.deps import Deps


async def search_knowledge_base(
    ctx: RunContext[Deps],
    query: str,
    top_k: int | None = None,
) -> list[KnowledgeChunk]:
    """Busca trechos relevantes na base de conhecimento sobre direito do consumidor.

    Args:
        query: Pergunta ou tema a ser buscado (ex: "prazo para reclamacao de vicio em produto duravel").
        top_k: Quantidade de trechos a retornar. Se omitido, usa o valor padrao de configuracao.

    Returns:
        Lista de `KnowledgeChunk` (fonte, texto) ordenados por relevancia
        decrescente. Retorna lista vazia `[]` quando a base nao tem
        trechos relevantes para a consulta (o adaptador trata o caso de
        "sem resultados" via o fallthrough de `relevant_chunks`).
    """
    retriever = ctx.deps.retriever
    configured_k = ctx.deps.settings.retrieval_top_k
    k = min(top_k, configured_k) if top_k is not None else configured_k
    if k < 1:
        k = configured_k

    nodes = await retriever.aretrieve(query)
    nodes = sorted(nodes, key=lambda n: getattr(n, "score", 0.0) or 0.0, reverse=True)[:k]

    if not nodes:
        return []

    chunks: list[KnowledgeChunk] = []
    for node in nodes:
        source = node.metadata.get("file_name") or node.node_id or "fonte desconhecida"
        text = node.get_content().strip()
        chunks.append(KnowledgeChunk(fonte=source, texto=text))
    return chunks
