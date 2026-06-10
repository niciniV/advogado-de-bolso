"""Indice vetorial baseado em ChromaDB + LlamaIndex com embeddings locais."""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

import chromadb
from chromadb.errors import NotFoundError
from llama_index.core import (
    Document,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.embeddings import BaseEmbedding
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from advogado_de_bolso.config import Settings

logger = logging.getLogger(__name__)


class KnowledgeIndex:
    """Gerencia o indice vetorial persistido em disco."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embed_model: BaseEmbedding | None = None
        self._chroma_collection: Any | None = None
        self._index: VectorStoreIndex | None = None

    def _get_embed_model(self) -> BaseEmbedding:
        if self._embed_model is None:
            os.environ.setdefault("HF_HOME", str(self._settings.hf_home))
            logger.info("Carregando modelo de embedding: %s", self._settings.embedding_model)
            self._embed_model = HuggingFaceEmbedding(
                model_name=self._settings.embedding_model,
                cache_folder=str(self._settings.hf_home),
            )
        return self._embed_model

    def _get_chroma_collection(self) -> Any:
        if self._chroma_collection is None:
            self._settings.chroma_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(self._settings.chroma_path))
            self._chroma_collection = client.get_or_create_collection(
                name=self._settings.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._chroma_collection

    def initialize(self) -> None:
        self._get_embed_model()
        self._get_chroma_collection()

    def build_or_load(self, documents: list[Document] | None = None) -> VectorStoreIndex:
        """Constroi um novo indice a partir de documentos OU carrega o existente."""
        embed_model = self._get_embed_model()

        chroma_collection = self._get_chroma_collection()
        vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        if documents:
            logger.info("Construindo indice com %d documento(s)...", len(documents))
            self._index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True,
            )
        else:
            logger.info("Carregando indice existente do ChromaDB.")
            self._index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
            )
        return self._index

    def replace_documents(self, documents: list[Document]) -> VectorStoreIndex:
        """Build a replacement first so a failed ingestion preserves the usable index."""
        embed_model = self._get_embed_model()
        self._settings.chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self._settings.chroma_path))
        replacement_name = f"{self._settings.collection_name[:45]}-next-{uuid4().hex[:8]}"
        replacement = client.get_or_create_collection(
            name=replacement_name,
            metadata={"hnsw:space": "cosine"},
        )
        try:
            vector_store = ChromaVectorStore(chroma_collection=replacement)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            next_index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=True,
            )
        except Exception:
            client.delete_collection(replacement_name)
            raise

        try:
            client.delete_collection(self._settings.collection_name)
        except NotFoundError:
            logger.info("Colecao anterior ainda nao existe; promovendo a nova.")
        replacement.modify(name=self._settings.collection_name)
        self._chroma_collection = replacement
        self._index = next_index
        return next_index

    def as_retriever(self) -> Any:
        if self._index is None:
            raise RuntimeError(
                "Indice nao inicializado. Chame build_or_load() antes de usar o retriever."
            )
        return self._index.as_retriever(similarity_top_k=self._settings.retrieval_top_k)
