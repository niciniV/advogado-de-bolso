# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Project Overview

Agentic chatbot for Brazilian consumer rights (CDC/Lei 8.078/90). Python 3.11+, Pydantic AI agent, ChromaDB RAG, FastAPI HTTP API, Rich CLI.

## File Map

| Path | Purpose |
|------|---------|
| `src/advogado_de_bolso/agent.py` | Main agent definition, system prompt, tool registration |
| `src/advogado_de_bolso/api.py` | FastAPI app, `/api/chat`, `/api/health`, session endpoints |
| `src/advogado_de_bolso/cli.py` | Interactive CLI with streaming, slash commands |
| `src/advogado_de_bolso/config.py` | `Settings` from env vars, `get_settings()` singleton |
| `src/advogado_de_bolso/deps.py` | `Deps` dataclass: settings + retriever injection |
| `src/advogado_de_bolso/service.py` | `ChatService`, `AgentChatBackend`, session management |
| `src/advogado_de_bolso/knowledge/index.py` | `KnowledgeIndex`: ChromaDB + LlamaIndex vector store |
| `src/advogado_de_bolso/knowledge/loader.py` | `load_documents()`, `load_urls()` for RAG ingestion |
| `src/advogado_de_bolso/tools/rag.py` | `search_knowledge_base()` - RAG retrieval tool |
| `src/advogado_de_bolso/tools/calculos.py` | `calcular_prazo_consumidor()` - CDC deadline math |
| `src/advogado_de_bolso/tools/redigir.py` | `redigir_documento()` - document drafting via sub-agent |
| `src/advogado_de_bolso/tools/revisor.py` | `review_response()`, `RevisionResult` - quality gate |
| `tests/conftest.py` | Shared fixtures: settings, mocks, deps, ctx |
| `tests/test_*.py` | Unit tests mirroring src structure |
| `pyproject.toml` | Build config, deps, ruff/pytest/mypy settings |
| `.opencode/plans/revised-integration-plan.md` | Active implementation plan (thin-index; full plan split into 25 topic files `00-…`-`24-…` plus `99-index.md` under `.opencode/plans/`) |
| `.opencode/AGENTS.md` | Child DOX for `.opencode/` (lists all 27 plan files and other `.opencode/` contents) |
| `.opencode/loop/` | Orchestration state, open issues, review log, fix log, decomposition proposal, split manifest |

## Child DOX Index

- `src/advogado_de_bolso/` - Main package: agent, service, CLI, API, config, deps
  - `src/advogado_de_bolso/knowledge/` - Vector index, document loaders, ChromaDB + LlamaIndex
  - `src/advogado_de_bolso/tools/` - Agent tools: RAG search, CDC calculations, drafting, review
- `tests/` - Test suite: unit tests, fixtures, coverage
- `.opencode/` - Opencode plan + loop bookkeeping (see `.opencode/AGENTS.md` for full file map)