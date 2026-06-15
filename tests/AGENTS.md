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
- `test_storage.py` - **NEW (batch 3).** Storage layer tests: atomic writes (unique `.{case_id}.{uuid4().hex}.tmp` paths, `os.replace` spy, concurrent saves to different cases never conflict, no torn JSON on same-case races), `list_all` (truncated `last_message` prefers `step_content` over `text`, deterministic `tag_text` precedence deadline > template_letter > None), `delete` (removes the file, returns `False` on missing), missing-file `load` returns `None`, path containment (`../../etc/passwd` and `/etc/passwd` raise `ValueError`), `save` creates parent directory if missing (ISSUE-005), `model_history` round-trip preserves `ModelMessage` structure but `ToolReturnPart.content` becomes a `dict` after JSON load (ISSUE-USR-016).
- `test_service.py` - **REWRITTEN (batch 4).** Old in-memory session tests dropped. New: constructor (creates directory, rejects non-positive history turns); `chat_structured` new session (creates case file, UUID round-trip, blocked first message does not create a file); `chat_structured` appends (second message appends, existing case ignores title/icon in chat requests); blocked envelope (blocked existing case keeps `chat_history` and `model_history` unchanged); per-case lock (concurrent calls serialized, retained lock after delete, concurrent delete+chat use same lock); ContextVar reset; `update_case_meta` (title/icon_name/response_style updates, missing case → KeyError, unknown field → ValueError, empty fields → ValueError, blank/over-120 title → ValueError, unknown icon/style → ValueError); `delete_case` (removes file, returns False on missing); `get_history` (returns chat_history, empty on missing); `list_cases` (lists all, empty); `model_history` persistence (with tool parts, JSON round-trip degrades `ToolReturnPart.content` to `dict` per ISSUE-USR-016, subsequent turn sees persisted history); helper unit tests (`_collect_tool_returns`, `_truncate_history_to_turns` keeps tool call/return paired); `AgentChatBackend` (returns prose + `new_messages`); `build_chat_service` wiring (passes `settings.cases_path`); Protocol surface checks.
- `test_api.py` - **REWRITTEN (batch 4).** Old `/api/chat`, `/api/sessions/{id}`, `/assets/*` tests dropped. New: `POST /api/chat/structured` (200 success, 422 blocked, 422 blank message, 422 over 8000 chars, 422 invalid icon_name/style/blank title/over 120 title, first-message metadata reaches service, 503 on unhandled exception), `GET /api/cases`, `GET /api/cases/{id}` (200/404/422 malformed UUID), `PATCH /api/cases/{id}` (title/icon_name/response_style/combined, 422 empty body, 422 unknown field, 404 missing, 422 service validation, 422 malformed UUID), `DELETE /api/cases/{id}` (204/404/422 malformed UUID), `GET /api/cases/{id}/history` (200/404/422 malformed UUID), SPA fallback (`GET /` returns index.html, `/api/chatt` 404, `/assets` mount served), CORS allows PATCH, old endpoints gone (`/api/chat` 404/405, `/api/sessions/{id}` 404/405), `CaseResponse` does not expose `model_history`.
- `test_agent.py` - **EXTENDED (batch 4).** Existing `test_build_agent_applies_preferred_configured_google_key` retained. Adds: `test_build_agent_registers_style_instructions` (asserts the `@agent.instructions` callback is registered and `STYLE_PROMPTS` has the three expected keys), `test_context_var_resets_after_request` (after `chat_structured(style="simples")` returns, `_current_style.get()` is `None` again), `test_context_var_visible_inside_chat_structured` (inside the backend call, `_current_style.get()` returns the value passed to `chat_structured`), `test_context_var_uses_case_default_when_request_omits_style` (persisted `case.response_style` is used as fallback), `test_blocked_response_does_not_create_case_file` (ISSUE-USR-004).
- `test_config.py` - **EXTENDED (batch 4).** Existing tests retained. Adds `test_default_cases_path_is_path` (default `cases_path` is a `Path` equal to `Path("./storage/cases")`) and `TestCasesPathOverride::test_cases_path_override_is_path` (`CASES_PATH` env override produces a `Path`).
- `test_calculos.py` - CDC deadline calculation logic (asserts on `DeadlineResult` fields for success; asserts `isinstance(result, str)` + substring matches for error paths)
- `test_revisor.py` - Response review tool
- `test_revision_result.py` - RevisionResult model validation
- `test_redigir.py` - Document drafting tool (asserts on `DraftedDocument.tipo`/`tom`/`destinatario`/`texto`; pins that `Tom` is the canonical `contracts.Tom` re-exported from `redigir`; pins that the "Responda APENAS com o texto final" sub-agent prompt is preserved per ISSUE-USR-017)
- `test_rag_tool.py` - RAG search tool (asserts on `list[KnowledgeChunk]`; first chunk's `fonte` matches the node's `file_name`; empty retriever result returns `[]` — never a sentinel chunk per ISSUE-USR-017)
- `test_knowledge_index.py` - KnowledgeIndex operations
- `test_cli.py` - **NEW (batch 5).** CLI tests. Uses a fake `Agent` whose `run_stream` returns an async context manager (`FakeStreamResult` / `_StreamCM` / `FakeAgent`) so the test can drive `_process_turn` without invoking a real Pydantic AI agent. Asserts: the CLI calls `review_response` with the generated question/response PLUS `settings.full_model_name` and `settings.build_model_settings()`; generated tokens/prose are NOT exposed before reviewer approval; approved response displays once and the case file is saved with both `chat_history` and `model_history` appended; blocked response returns only `REVIEW_BLOCKED_MESSAGE` and the case file is NOT created/modified; two approved turns reuse the same canonical UUID, preserve the original `created_at`, advance `updated_at`, and append to both histories; `/limpar` starts a new UUID/Case WITHOUT overwriting the prior saved case file; `REVIEW_BLOCKED_MESSAGE` is the same string as `service.REVIEW_BLOCKED_MESSAGE`. The testing strategy (extract a pure async `_process_turn` helper so the Rich UI loop is a thin wrapper) is documented in the test file's docstring.

## Verification

- `pytest tests/ -v` - Run all tests
- `pytest tests/ --cov=advogado_de_bolso` - Coverage report
