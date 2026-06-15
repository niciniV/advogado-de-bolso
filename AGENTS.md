# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Project Overview

Agentic chatbot for Brazilian consumer rights (CDC/Lei 8.078/90). Python 3.11–3.14, Pydantic AI 1.106+ agent, ChromaDB RAG, FastAPI HTTP API, Rich CLI. Implementation follows a 9-batch gated plan (see `.opencode/plans/20-implementation-order.md`); batch 1 introduced typed tool return envelopes in `src/advogado_de_bolso/contracts.py` (DeadlineResult, DraftedDocument, KnowledgeChunk + Tom/TipoPrazo aliases). The downstream adapter, service rewrite, and storage layer are not yet wired — `agent.py`, `service.py`, `api.py`, `cli.py` are still under the pre-batch-4 design and will be rewired in later batches.

## File Map

| Path | Purpose |
|------|---------|
| `src/advogado_de_bolso/agent.py` | Main agent definition, system prompt, tool registration (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/api.py` | FastAPI app, `/api/chat`, `/api/health`, session endpoints (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/cli.py` | Interactive CLI with streaming, slash commands (still under the pre-batch-4 design; rewired in batch 5) |
| `src/advogado_de_bolso/config.py` | `Settings` from env vars, `get_settings()` singleton |
| `src/advogado_de_bolso/contracts.py` | **NEW (batch 1).** Typed tool return envelopes: `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` (Pydantic BaseModel) plus canonical `TipoPrazo` / `Tom` literal aliases. Tool success paths return these; error paths return plain `str`. |
| `src/advogado_de_bolso/deps.py` | `Deps` dataclass: settings + retriever injection |
| `src/advogado_de_bolso/service.py` | `ChatService`, `AgentChatBackend`, session management (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/knowledge/index.py` | `KnowledgeIndex`: ChromaDB + LlamaIndex vector store |
| `src/advogado_de_bolso/knowledge/loader.py` | `load_documents()`, `load_urls()` for RAG ingestion |
| `src/advogado_de_bolso/tools/rag.py` | `search_knowledge_base()` - RAG retrieval tool; returns `list[KnowledgeChunk]` (empty list when no hits, never a sentinel chunk) |
| `src/advogado_de_bolso/tools/calculos.py` | `calcular_prazo_consumidor()` - CDC deadline math; returns `DeadlineResult` on success, `str` on error |
| `src/advogado_de_bolso/tools/redigir.py` | `redigir_documento()` - document drafting via sub-agent; returns `DraftedDocument`; imports canonical `Tom` from `contracts` and re-exports it |
| `src/advogado_de_bolso/tools/revisor.py` | `review_response()`, `RevisionResult` - quality gate |
| `tests/conftest.py` | Shared fixtures: settings, mocks, deps, ctx |
| `tests/test_*.py` | Unit tests mirroring src structure |
| `pyproject.toml` | Build config, deps, ruff/pytest/mypy settings. `requires-python = ">=3.11,<3.15"`; `pydantic-ai>=1.106.0,<2.0.0` (batch 1 pin). |
| `.opencode/plans/revised-integration-plan.md` | Active implementation plan (thin-index; full plan split into 25 topic files `00-…`-`24-…` plus `99-index.md` under `.opencode/plans/`) |
| `.opencode/AGENTS.md` | Child DOX for `.opencode/` (lists all 27 plan files and other `.opencode/` contents) |
| `.opencode/loop/` | Orchestration state, open issues, review log, fix log, decomposition proposal, split manifest |

## Child DOX Index

- `src/advogado_de_bolso/` - Main package: agent, service, CLI, API, config, deps
  - `src/advogado_de_bolso/knowledge/` - Vector index, document loaders, ChromaDB + LlamaIndex
  - `src/advogado_de_bolso/tools/` - Agent tools: RAG search, CDC calculations, drafting, review
- `tests/` - Test suite: unit tests, fixtures, coverage
- `.opencode/` - Opencode plan + loop bookkeeping (see `.opencode/AGENTS.md` for full file map)