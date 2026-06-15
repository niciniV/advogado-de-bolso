# tests - Test Suite

## Purpose

Unit and integration tests for the Advogado de Bolso application. Validates tool logic, service behavior, API endpoints, configuration, and knowledge base operations.

## Ownership

- Test fixtures and shared mocks in `conftest.py`
- Individual test modules mirror `src/advogado_de_bolso/` structure

## Local Contracts

- Framework: pytest with pytest-asyncio (auto mode)
- Coverage: pytest-cov
- All tests run via `pytest tests/`
- Python path configured for local dev: `pythonpath = ["src"]`
- CI must install package in editable mode: `pip install -e ".[dev]"`

## Work Guidance

### Fixtures (`conftest.py`)
- `settings` - Pre-configured `Settings` with test values
- `mock_retriever` - Async mock returning empty results
- `deps` - `Deps` instance with mocked retriever
- `ctx` - Mocked `RunContext` for tool tests
- `mock_agent_run` - Mocked agent result
- `mock_revision_result_approved` / `mock_revision_result_needs_fix` - Review results
- `sample_data_aquisicao` / `sample_data_compra` - Sample dates

### Test Files
- `test_adapter.py` - **NEW (batch 2).** Adapter golden tests; covers `StructuredChatRequest/Response`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest` wire types; `extract_structured_response` dispatch by `tool_name` + `isinstance`; the three helpers (`_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`); the ISSUE-USR-010 regex fix (`"1. The customer should..."` NOT extracted, `"Posso cancelar a compra?"` full question captured); empty-prose `Análise inicial` fallback (ISSUE-004); unknown-tool-name WARNING log (ISSUE-DS-006); tuple-as-Sequence for `search_knowledge_base` (ISSUE-M3-010); the `tool_plain` raw-object round-trip contract (ISSUE-006 / ISSUE-USR-009) exercised against a real Pydantic AI `TestModel` agent.
- `test_service.py` - ChatService session management and chat flow
- `test_api.py` - FastAPI endpoint tests (health, chat, clear session)
- `test_agent.py` - Agent construction and tool registration
- `test_config.py` - Settings validation and properties
- `test_calculos.py` - CDC deadline calculation logic (asserts on `DeadlineResult` fields for success; asserts `isinstance(result, str)` + substring matches for error paths)
- `test_revisor.py` - Response review tool
- `test_revision_result.py` - RevisionResult model validation
- `test_redigir.py` - Document drafting tool (asserts on `DraftedDocument.tipo`/`tom`/`destinatario`/`texto`; pins that `Tom` is the canonical `contracts.Tom` re-exported from `redigir`; pins that the "Responda APENAS com o texto final" sub-agent prompt is preserved per ISSUE-USR-017)
- `test_rag_tool.py` - RAG search tool (asserts on `list[KnowledgeChunk]`; first chunk's `fonte` matches the node's `file_name`; empty retriever result returns `[]` — never a sentinel chunk per ISSUE-USR-017)
- `test_knowledge_index.py` - KnowledgeIndex operations

## Verification

- `pytest tests/ -v` - Run all tests
- `pytest tests/ --cov=advogado_de_bolso` - Coverage report
