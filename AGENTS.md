# DOX framework

- DOX is highly performant AGENTS.md hierarchy installed here
- Agent must follow DOX instructions across any edits

## Project Overview

Agentic chatbot for Brazilian consumer rights (CDC/Lei 8.078/90). Python 3.11–3.14, Pydantic AI 1.106+ agent, ChromaDB RAG, FastAPI HTTP API, Rich CLI. Implementation follows a 9-batch gated plan (see `.opencode/plans/20-implementation-order.md`); batch 1 introduced typed tool return envelopes in `src/advogado_de_bolso/contracts.py` (DeadlineResult, DraftedDocument, KnowledgeChunk + Tom/TipoPrazo aliases), batch 2 added wire types (`schemas.py`) and the LLM-output → wire-response adapter (`adapter.py`) with golden tests in `tests/test_adapter.py`, **batch 3 added per-case JSON persistence (`src/advogado_de_bolso/storage/cases.py`) with `Case` model + `load`/`save`/`delete`/`list_all` and the storage golden tests in `tests/test_storage.py`**. The downstream service rewrite, HTTP/CLI rewires, and frontend rewires are not yet wired — `agent.py`, `service.py`, `api.py`, `cli.py` are still under the pre-batch-4 design and will be rewired in later batches.

## File Map

| Path | Purpose |
|------|---------|
| `src/advogado_de_bolso/agent.py` | Main agent definition, system prompt, tool registration (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/adapter.py` | **NEW (batch 2).** `extract_structured_response` + 3 helpers (`_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`). Pure function: dispatches on `tool_name` + `isinstance`; unknown tools log WARNING; QUESTION_PATTERNS pins the ISSUE-USR-010 regex fix. |
| `src/advogado_de_bolso/api.py` | FastAPI app, `/api/chat`, `/api/health`, session endpoints (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/cli.py` | Interactive CLI with streaming, slash commands (still under the pre-batch-4 design; rewired in batch 5) |
| `src/advogado_de_bolso/config.py` | `Settings` from env vars, `get_settings()` singleton |
| `src/advogado_de_bolso/contracts.py` | Typed tool return envelopes: `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` (Pydantic BaseModel) plus canonical `TipoPrazo` / `Tom` literal aliases. Tool success paths return these; error paths return plain `str`. |
| `src/advogado_de_bolso/deps.py` | `Deps` dataclass: settings + retriever injection |
| `src/advogado_de_bolso/schemas.py` | **NEW (batch 2).** Wire types for the HTTP API: `StructuredChatRequest/Response`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest`. All fields snake_case. `StringConstraints` for `message`/`title`; `Literal` for `icon_name`/`response_style`; `ConfigDict(extra="forbid")` + `model_validator` on `UpdateCaseRequest` (USR-005). `StructuredChatResponse.updated_at` and `.chat_history` have assembly-safe defaults (ISSUE-USR-015). |
| `src/advogado_de_bolso/service.py` | `ChatService`, `AgentChatBackend`, session management (still under the pre-batch-4 design; rewired in batch 4) |
| `src/advogado_de_bolso/storage/cases.py` | **NEW (batch 3).** Per-case JSON persistence: `Case` model + `load` / `save` / `delete` / `list_all`; all four functions take `cases_path: Path` keyword-only (ISSUE-USR-007); atomic writes use `.{case_id}.{uuid4().hex}.tmp` + `os.replace`; path-containment via `is_relative_to` (ISSUE-USR-001); directory creation on `save` (ISSUE-005); `<1000` case scalability constraint with soft INFO warning at >500 (ISSUE-DS-007). |
| `src/advogado_de_bolso/storage/__init__.py` | **NEW (batch 3).** Empty package init for the storage subpackage. |
| `src/advogado_de_bolso/knowledge/index.py` | `KnowledgeIndex`: ChromaDB + LlamaIndex vector store |
| `src/advogado_de_bolso/knowledge/loader.py` | `load_documents()`, `load_urls()` for RAG ingestion |
| `src/advogado_de_bolso/tools/rag.py` | `search_knowledge_base()` - RAG retrieval tool; returns `list[KnowledgeChunk]` (empty list when no hits, never a sentinel chunk) |
| `src/advogado_de_bolso/tools/calculos.py` | `calcular_prazo_consumidor()` - CDC deadline math; returns `DeadlineResult` on success, `str` on error |
| `src/advogado_de_bolso/tools/redigir.py` | `redigir_documento()` - document drafting via sub-agent; returns `DraftedDocument`; imports canonical `Tom` from `contracts` and re-exports it |
| `src/advogado_de_bolso/tools/revisor.py` | `review_response()`, `RevisionResult` - quality gate |
| `tests/conftest.py` | Shared fixtures: settings, mocks, deps, ctx |
| `tests/test_adapter.py` | **NEW (batch 2).** Golden tests for the adapter and wire schemas; pins ISSUE-USR-010 regex fix, ISSUE-004 empty-prose fallback, ISSUE-DS-006 unknown-tool WARNING, ISSUE-M3-010 tuple-as-Sequence, and the ISSUE-006 / ISSUE-USR-009 `tool_plain` raw-object round-trip against a real Pydantic AI `TestModel` agent. |
| `tests/test_storage.py` | **NEW (batch 3).** Storage layer tests: atomic writes use unique `.{case_id}.{uuid4().hex}.tmp` paths and `os.replace`; concurrent saves to different cases never conflict; `delete` removes the file (returns `False` on missing); `list_all` returns `CaseSummary` per JSON file with `last_message` (last assistant `step_content` || `text`, truncated to 80 chars) and `tag_text` (deadline > template_letter > None); missing file → `load` returns `None`; path containment: `../../etc/passwd` and `/etc/passwd` raise `ValueError`; `save` creates parent directory if missing; `model_history` round-trip preserves `ModelMessage` structure but `ToolReturnPart.content` is a `dict` after JSON load (ISSUE-USR-016). |
| `tests/test_*.py` | Unit tests mirroring src structure |
| `pyproject.toml` | Build config, deps, ruff/pytest/mypy settings. `requires-python = ">=3.11,<3.15"`; `pydantic-ai>=1.106.0,<2.0.0` (batch 1 pin). |
| `.opencode/plans/revised-integration-plan.md` | Active implementation plan (thin-index; full plan split into 25 topic files `00-…`-`24-…` plus `99-index.md` under `.opencode/plans/`) |
| `.opencode/AGENTS.md` | Child DOX for `.opencode/` (lists all 27 plan files and other `.opencode/` contents) |
| `.opencode/loop/` | Orchestration state, open issues, review log, fix log, decomposition proposal, split manifest |

## Child DOX Index

- `src/advogado_de_bolso/` - Main package: agent, service, CLI, API, config, deps
  - `src/advogado_de_bolso/knowledge/` - Vector index, document loaders, ChromaDB + LlamaIndex
  - `src/advogado_de_bolso/storage/` - Per-case JSON persistence (batch 3)
  - `src/advogado_de_bolso/tools/` - Agent tools: RAG search, CDC calculations, drafting, review
- `tests/` - Test suite: unit tests, fixtures, coverage
- `.opencode/` - Opencode plan + loop bookkeeping (see `.opencode/AGENTS.md` for full file map)