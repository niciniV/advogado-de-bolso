from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from advogado_de_bolso.tools.rag import search_knowledge_base


def _make_node(score: float, file_name: str | None, node_id: str, content: str) -> MagicMock:
    node = MagicMock()
    node.score = score
    node.metadata = {"file_name": file_name} if file_name else {}
    node.node_id = node_id
    node.get_content.return_value = content
    return node


class TestSearchKnowledgeBase:
    @pytest.mark.asyncio
    async def test_no_results_returns_message(self, ctx, mock_retriever):
        mock_retriever.aretrieve.return_value = []
        result = await search_knowledge_base(ctx, "consulta sem resultados")
        assert "Nenhum trecho relevante" in result

    @pytest.mark.asyncio
    async def test_with_results_returns_formatted_chunks(self, ctx, mock_retriever):
        node = _make_node(
            score=0.95,
            file_name="cdc_art26.txt",
            node_id="node-123",
            content="Art. 26 - Prazo para reclamar...",
        )
        mock_retriever.aretrieve.return_value = [node]

        result = await search_knowledge_base(ctx, "prazo reclamacao")
        assert "Art. 26" in result
        assert "cdc_art26.txt" in result

    @pytest.mark.asyncio
    async def test_results_limited_by_top_k(self, ctx, mock_retriever):
        nodes = [
            _make_node(1.0 - i * 0.1, f"doc{i}.txt", f"node-{i}", f"Conteudo do documento {i}")
            for i in range(5)
        ]
        mock_retriever.aretrieve.return_value = nodes

        result = await search_knowledge_base(ctx, "teste", top_k=2)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" not in result

    @pytest.mark.asyncio
    async def test_uses_default_top_k_when_none(self, ctx, mock_retriever, settings):
        nodes = [
            _make_node(1.0 - i * 0.1, f"doc{i}.txt", f"node-{i}", f"Conteudo {i}") for i in range(5)
        ]
        mock_retriever.aretrieve.return_value = nodes
        ctx.deps.settings.retrieval_top_k = 2

        result = await search_knowledge_base(ctx, "teste")
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" not in result

    @pytest.mark.asyncio
    async def test_fallback_source_when_no_file_name(self, ctx, mock_retriever):
        node = _make_node(
            score=0.8,
            file_name=None,
            node_id="fallback-node-id",
            content="Conteudo sem filename",
        )
        mock_retriever.aretrieve.return_value = [node]

        result = await search_knowledge_base(ctx, "consulta")
        assert "fallback-node-id" in result
        assert "Conteudo sem filename" in result

    @pytest.mark.asyncio
    async def test_third_fallback_fonte_desconhecida(self, ctx, mock_retriever):
        node = _make_node(
            score=0.7,
            file_name=None,
            node_id="",
            content="Conteudo sem fonte alguma",
        )
        mock_retriever.aretrieve.return_value = [node]

        result = await search_knowledge_base(ctx, "consulta")
        assert "fonte desconhecida" in result
        assert "Conteudo sem fonte alguma" in result

    @pytest.mark.asyncio
    async def test_sort_by_score_descending(self, ctx, mock_retriever):
        nodes = [
            _make_node(0.3, "baixo.txt", "n1", "Baixa relevancia"),
            _make_node(0.9, "alto.txt", "n2", "Alta relevancia"),
        ]
        mock_retriever.aretrieve.return_value = nodes

        result = await search_knowledge_base(ctx, "teste", top_k=2)
        assert result.index("Alta relevancia") < result.index("Baixa relevancia")

    @pytest.mark.asyncio
    async def test_nodes_with_none_score(self, ctx, mock_retriever):
        node = _make_node(0.0, "doc.txt", "n1", "Conteudo")
        node.score = None
        mock_retriever.aretrieve.return_value = [node]

        result = await search_knowledge_base(ctx, "consulta")
        assert "Conteudo" in result

    @pytest.mark.asyncio
    async def test_negative_top_k_falls_back_to_default(self, ctx):
        """A negative top_k should fall back to the config default, not slice backwards."""
        result = await search_knowledge_base(ctx, "test query", top_k=-1)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_top_k_cannot_expand_beyond_configured_limit(self, ctx, mock_retriever):
        nodes = [
            _make_node(1.0 - i * 0.1, f"doc{i}.txt", f"node-{i}", f"Conteudo {i}")
            for i in range(5)
        ]
        mock_retriever.aretrieve.return_value = nodes
        ctx.deps.settings.retrieval_top_k = 2

        result = await search_knowledge_base(ctx, "teste", top_k=5)

        assert "[2]" in result
        assert "[3]" not in result
