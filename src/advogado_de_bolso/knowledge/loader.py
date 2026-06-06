"""Carregadores de documentos para a base de conhecimento.

Para adicionar fontes, basta colocar arquivos em DATA_PATH (padrao ./data/raw).
Extensoes suportadas: .pdf, .md, .markdown, .html, .htm, .txt
"""

from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core import Document, SimpleDirectoryReader

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".pdf",
    ".md",
    ".markdown",
    ".html",
    ".htm",
    ".txt",
)


def load_documents(data_path: Path) -> list[Document]:
    """Carrega todos os arquivos suportados de `data_path` (recursivo)."""
    if not data_path.exists():
        logger.warning("Caminho de dados nao existe: %s", data_path)
        return []

    reader = SimpleDirectoryReader(
        input_dir=str(data_path),
        required_exts=list(SUPPORTED_EXTENSIONS),
        recursive=True,
        filename_as_id=True,
    )
    docs = reader.load_data()
    for d in docs:
        d.metadata.setdefault("file_name", "desconhecido")
    return docs


def load_urls(urls: list[str]) -> list[Document]:
    """Carrega paginas web como documentos (uso via CLI futuramente)."""
    from llama_index.readers.web import SimpleWebPageReader

    return SimpleWebPageReader(html_to_text=True).load_data(urls=urls)
