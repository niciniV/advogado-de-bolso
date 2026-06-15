# knowledge - Knowledge Base

## Purpose

Manages the vector index for RAG (Retrieval-Augmented Generation). Stores and retrieves legal documents, jurisprudence, and consumer protection materials using ChromaDB + LlamaIndex with local HuggingFace embeddings.

## Ownership

- Vector index lifecycle: build, load, replace, retrieve
- Document loading from local files and web URLs
- ChromaDB persistence and collection management

## Local Contracts

- Embedding model: `BAAI/bge-m3` (configurable via `EMBEDDING_MODEL`)
- Vector store: ChromaDB with cosine similarity
- Supported document formats: `.pdf`, `.md`, `.markdown`, `.html`, `.htm`, `.txt`
- Data directory: `DATA_PATH` (default `./data/raw`)
- ChromaDB storage: `CHROMA_PATH` (default `./storage/chroma`)
- Index must be built/loaded before any retrieval call

## Work Guidance

- `KnowledgeIndex` is the main entry point - wraps ChromaDB + LlamaIndex
- `build_or_load()` creates index from documents or loads existing from disk
- `replace_documents()` does safe replacement (builds new collection, then swaps)
- `as_retriever()` returns a LlamaIndex retriever for use in `Deps`
- `load_documents()` reads all supported files from `data_path` recursively
- `load_urls()` fetches web pages as documents (future CLI use)
- Embeddings are cached in `HF_HOME` (default `./storage/hf_cache`)

## Verification

- Test that `build_or_load()` succeeds with sample documents
- Test that `replace_documents()` preserves old index on failure
- Test retrieval returns relevant chunks for known queries
