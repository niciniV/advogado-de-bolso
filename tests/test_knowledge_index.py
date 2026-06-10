from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from advogado_de_bolso.knowledge.index import KnowledgeIndex


class TestKnowledgeIndexInit:
    def test_as_retriever_raises_if_not_initialized(self, settings):
        index = KnowledgeIndex(settings)
        with pytest.raises(RuntimeError, match="nao inicializado"):
            index.as_retriever()

    def test_initial_state(self, settings):
        index = KnowledgeIndex(settings)
        assert index._index is None
        assert index._embed_model is None


class TestKnowledgeIndexBuildOrLoad:
    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_empty_documents_list_falls_to_load(self, MockVSI, MockChroma, MockHF, settings):
        MockVSI.from_vector_store.return_value = MagicMock()
        index = KnowledgeIndex(settings)
        result = index.build_or_load(documents=[])
        MockVSI.from_vector_store.assert_called_once()
        assert result is not None

    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_build_with_documents(self, MockVSI, MockChroma, MockHF, settings):
        MockVSI.from_documents.return_value = MagicMock()
        index = KnowledgeIndex(settings)
        docs = [MagicMock()]
        result = index.build_or_load(documents=docs)
        MockVSI.from_documents.assert_called_once()
        assert result is not None

    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_load_existing(self, MockVSI, MockChroma, MockHF, settings):
        MockVSI.from_vector_store.return_value = MagicMock()
        index = KnowledgeIndex(settings)
        result = index.build_or_load(documents=None)
        MockVSI.from_vector_store.assert_called_once()
        assert result is not None

    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_build_called_only_once(self, MockVSI, MockChroma, MockHF, settings):
        MockVSI.from_documents.return_value = MagicMock()
        index = KnowledgeIndex(settings)
        index.build_or_load(documents=[MagicMock()])
        index.build_or_load(documents=[MagicMock()])
        assert MockVSI.from_documents.call_count == 2

    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_replace_documents_deletes_stale_collection(
        self, MockVSI, MockChroma, MockHF, settings
    ):
        client = MockChroma.return_value
        replacement = client.get_or_create_collection.return_value
        MockVSI.from_documents.return_value = MagicMock()
        index = KnowledgeIndex(settings)

        result = index.replace_documents([MagicMock()])

        client.delete_collection.assert_called_once_with(settings.collection_name)
        client.get_or_create_collection.assert_called_once()
        replacement.modify.assert_called_once_with(name=settings.collection_name)
        MockVSI.from_documents.assert_called_once()
        assert result is not None

    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_replace_documents_preserves_old_collection_when_build_fails(
        self, MockVSI, MockChroma, MockHF, settings
    ):
        MockVSI.from_documents.side_effect = RuntimeError("embedding failure")
        index = KnowledgeIndex(settings)

        with pytest.raises(RuntimeError, match="embedding failure"):
            index.replace_documents([MagicMock()])

        deleted_names = [call.args[0] for call in MockChroma.return_value.delete_collection.call_args_list]
        assert settings.collection_name not in deleted_names


class TestKnowledgeIndexRetriever:
    @patch("advogado_de_bolso.knowledge.index.HuggingFaceEmbedding")
    @patch("advogado_de_bolso.knowledge.index.chromadb.PersistentClient")
    @patch("advogado_de_bolso.knowledge.index.VectorStoreIndex")
    def test_as_retriever_after_build(self, MockVSI, MockChroma, MockHF, settings):
        mock_index = MagicMock()
        mock_retriever = MagicMock()
        mock_index.as_retriever.return_value = mock_retriever
        MockVSI.from_documents.return_value = mock_index

        index = KnowledgeIndex(settings)
        index.build_or_load(documents=[MagicMock()])
        retriever = index.as_retriever()

        assert retriever == mock_retriever
        mock_index.as_retriever.assert_called_once_with(similarity_top_k=settings.retrieval_top_k)
