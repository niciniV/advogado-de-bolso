# 15-backend-tests.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1017-1098)
**In this file:** All backend test-file specs — `test_adapter.py`, `test_storage.py`, `test_calculos.py`, `test_redigir.py`, `test_rag_tool.py`, `test_api.py`, `test_service.py`, `test_agent.py`, `test_cli.py`. Roughly 80 lines of bullet spec plus section headers.
**Related files:** [03-adapter.md](./03-adapter.md) (the module under `test_adapter.py` test), [04-storage.md](./04-storage.md) (the storage functions under `test_storage.py` test), [06-service-class.md](./06-service-class.md) (the `ChatService` under `test_service.py` test), [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) (the agent + `_current_style` under `test_agent.py` test), [09-cli-config-deps.md](./09-cli-config-deps.md) (the CLI behavior under `test_cli.py` test), [08-api.md](./08-api.md) (the HTTP surface under `test_api.py` test).

### `tests/test_adapter.py` (new)
Golden tests covering:
- DeadlineResult turn → `structured.deadline` populated.
- DraftedDocument turn → `structured.template_letter == doc.texto`.
- Both in one turn → both populated.
- search_knowledge_base empty list → no `relevant_content`, no error.
- search_knowledge_base with chunks → `relevant_title` = first `fonte`, `relevant_content` = joined first two `texto`s.
- search_knowledge_base returning a `tuple` (Sequence) → accepted (ISSUE-M3-010).
- `calcular_prazo_consumidor` returning a **string** (error path) → `structured.deadline is None`, no crash.
- Reviewer-blocked case → `structured.blocked is True`, `structured.blocked_message` is set.
- Constructing `StructuredChatResponse` inside the adapter succeeds before service enrichment because `updated_at` and `chat_history` have assembly-safe defaults; service tests assert those placeholders are overwritten before API return.
- `prose` containing "Posso..." questions → `questions` is non-empty.
- **`prose` with "Posso cancelar a compra?"** (ISSUE-USR-010): assert the extracted question is `"Posso cancelar a compra?"` (or the rstrip'd form `"Posso cancelar a compra"` with the trailing `?` re-appended by the helper), NOT `"Posso"`. Pins the regex fix.
- **`prose` with "1. The customer should..."** (ISSUE-USR-010): assert the numbered list item is NOT extracted as a question (the new pattern requires the item to end in "?"). Pins the regex fix for non-question numbered items.
- `prose` with no patterns → `questions = []`, `quick_replies` falls back to defaults.
- **Empty prose** → `step_title == "Análise inicial"`, `step_content == ""` (ISSUE-004).
- **Unknown tool name** in the `ToolReturnPart.tool_name` → the `else` branch logs a WARNING; no exception raised; `structured` is otherwise unchanged (ISSUE-DS-006).
- **`tool_plain` raw-object contract** (ISSUE-006 + ISSUE-USR-009): the test MUST exercise the **real Pydantic AI tool-execution path**, not a hand-constructed `ToolReturnPart`. The previous spec ("construct a fake `ToolReturnPart` whose `content` is a `DeadlineResult` instance, assert `isinstance(part.content, DeadlineResult)`") was tautological — it only proved Python can hold a reference to a typed object inside a dataclass field. The new spec:
  1. Register a real `@agent.tool_plain` function that returns a `DeadlineResult` (e.g., a stub `def stub_calcular(...) -> DeadlineResult: return DeadlineResult(...)`).
  2. Call `await agent.run("user message that triggers the tool")` against a real (or `TestModel`) LLM.
  3. Inspect `result.new_messages()` and assert the last `ModelResponse.parts[-1]` is a `ToolCallPart` AND the immediately-following `ModelRequest.parts[-1]` is a `ToolReturnPart` whose `content` is an **`isinstance` of `DeadlineResult`** (NOT a `dict`).
  4. This pins the actual `tool_plain` → `ToolReturnPart` round-trip. If Pydantic AI changes and starts stringifying `tool_plain` returns, this test will fail loudly.
   5. Note: even with the real round-trip, JSON serialize/deserialize (`all_messages_json` → `ModelMessagesTypeAdapter.validate_python`) will produce a plain `dict` from the typed object on reload — the test therefore only pins the **in-memory** behavior, not persistence. A separate test pins the persistence shape (the `ModelMessage` structure with `ToolCallPart` + `ToolReturnPart` survives the storage layer round-trip, but the `ToolReturnPart.content` is loaded as a `dict`, NOT as a `DeadlineResult`).

### `tests/test_storage.py` (new)
- Atomic write uses a unique same-directory `.tmp` path and `os.replace`; two concurrent saves never share a temp filename or produce malformed JSON.
- `delete_case` removes the file. Lock-registry behavior is tested at the service layer.
- `list_all` returns the right summaries.
- Missing file → `load` returns `None`, not raise.

### `tests/test_calculos.py` (rewrite)
All string-content assertions become field assertions:
- `assert result.tipo_prazo == "arrependimento"`
- `assert result.dias == 7`
- `assert result.base_legal == "CDC art. 49"`
- For error cases, assert `isinstance(result, str)` and substring matches.

### `tests/test_redigir.py` (rewrite)
- Mock the sub-agent to return a string.
- Assert the outer `redigir_documento` returns a `DraftedDocument`.
- Assert `result.tipo == <input>`, `result.tom == <input>`, `result.destinatario == <input>`, `result.texto == "texto gerado..."`.

### `tests/test_rag_tool.py` (rewrite)
- Mock the retriever to return nodes.
- Assert `search_knowledge_base` returns `list[KnowledgeChunk]`.
- Assert the first chunk's `fonte` is the node's `file_name`.
- Empty result → `[]` (ISSUE-USR-017: empty RAG result is the empty list `[]`, NOT a sentinel `KnowledgeChunk(fonte="sistema", ...)`). The test asserts `search_knowledge_base` returns an empty list, and the adapter handles the empty list via the `relevant_chunks` fallthrough (no `relevant_title`, no `relevant_content`). The system prompt acknowledges the empty result with the "no relevant info" message.

### `tests/test_api.py` (rewrite)
- Drop tests for `/api/chat`, `/api/sessions/{id}`, `/assets/*`.
- Add tests for `/api/chat/structured` (200 success, 422 blocked, 422 validation error).
- Add tests for `GET /api/cases`, `GET /api/cases/{id}`, `PATCH /api/cases/{id}`, `DELETE /api/cases/{id}`, `GET /api/cases/{id}/history`.
- For every `/api/cases/{case_id}` endpoint, assert a malformed non-UUID path parameter returns 422 before the service is called.
- Add a test for the SPA fallback (`GET /` returns index.html, `GET /api/typo` returns 404).
- **PATCH body test** (ISSUE-USR-005): assert that `PATCH /api/cases/{id}` with `UpdateCaseRequest { title: "X" }`, `{ icon_name: "shopping_bag" }`, `{ response_style: "simples" }`, and any combination thereof, all succeed; assert that an empty body `{ }` returns 422 (the `model_validator` rejects "no fields set"); assert that an unknown field returns 422.
- **First-message metadata validation test** (ISSUE-REVIEW-007): assert `POST /api/chat/structured` rejects blank/over-120-character `title`, unknown `icon_name`, invalid `response_style`, blank `message`, and messages over 8,000 characters with 422 before the service is called. Assert valid auto-create metadata reaches the service stripped and unchanged.
- **GET single-case test** (ISSUE-USR-005): assert `GET /api/cases/{id}` returns a `CaseResponse` for an existing case and 404 for a missing case.
- Assert `CaseResponse` contains `created_at`, `updated_at`, `icon_name`, `response_style`, and mapped `chat_history`, matching what `mapCaseResponse` requires.
- Assert chat requests carrying `title` or `icon_name` for an existing UUID do not change persisted metadata; only PATCH may change those fields.
- **Blocked-first-message test** (ISSUE-USR-004): assert that a blocked first message returns the full `StructuredChatResponse` envelope with status 422, `session_id`, `blocked=true`, `blocked_message`, and empty/unchanged history; assert NO `{session_id}.json` file is created on disk (the service skips `cases.save` for blocked new cases).

### `tests/test_service.py` (rewrite)
- `ChatService` no longer has `chat`, `clear_session`, `session_history`, `session_count`, `_max_sessions`, `_evict_old_sessions`.
- New tests: `chat_structured` with new session creates a case file; second message appends; per-case lock serializes concurrent calls; reviewer-blocked returns blocked; `delete_case` removes the case file while retaining the same lock object.
- **Blocked existing-case test**: after one approved persisted turn, block the next turn and assert neither `chat_history` nor `model_history` changes on disk; the rejected prose/tool returns are absent from the 422 response and the next backend history.
- Test the `ContextVar` reset: after `chat_structured(style="simples")`, the style is reset (no leakage between requests).
- **`model_history` persistence** (ISSUE-M3-001): after a turn that included a `ToolCallPart`/`ToolReturnPart`, the case file on disk contains the full `ModelMessage` list with the tool parts. A subsequent `chat_structured` call passes that list back to the backend. Assert via inspecting `case.model_history` after the first call, then mock the second call to capture the `history` argument and assert it matches.
- **`model_history` JSON-roundtrip shape** (ISSUE-USR-016): the persistence test for the tool return MUST NOT require `isinstance(content, DeadlineResult)` after a JSON load. The plan's `test_adapter.py` spec acknowledges that JSON serialize/deserialize produces a plain `dict` from the typed object on reload. The relaxed assertion is: after `cases.save(case)` followed by `cases.load(case_id)`, the reloaded `case.model_history` contains a `ModelRequest` whose last part is a `ToolReturnPart` whose `content` is a `dict` (NOT a `DeadlineResult`) with the same field values as the original (`data_inicio`, `data_limite`, `dias`, `tipo_prazo`, `base_legal`, `item_label`, `vicio_oculto`, `nota`). This pins the persistence structure without making an impossible typed-identity claim. The in-memory `tool_plain` round-trip test continues to assert `isinstance(content, DeadlineResult)` because that test does not round-trip through JSON.
- **`update_case_meta` wiring** (ISSUE-M3-008): the PATCH endpoint calls `update_case_meta(case_id, title="...")`, and the case on disk reflects the new title. Title validation (non-empty, max length) lives in `update_case_meta`, not the endpoint.
- **Retained-lock concurrency regression**: start one operation holding a case lock, queue `delete_case`, then queue a new `chat_structured` for the same UUID. Assert all three operations use the exact same lock object and execute serially. After deletion, the UUID remains in `_case_locks`; this is intentional and prevents the old-lock/new-lock race.

### `tests/test_agent.py` (extend)
- Existing test stays.
- Add: `test_build_agent_registers_style_instructions` — assert the agent has an instructions function registered.
- Add: `test_context_var_resets_after_request` (ISSUE-DS-008) — after `chat_structured(style="simples")` returns, `_current_style.get()` is `None` again (no leakage to the next request). Use a real `ChatService` with a fake `ChatBackend` and a fake `ReviewerLike`.
- Add: `test_context_var_visible_inside_chat_structured` (ISSUE-DS-008) — inside the backend call, `_current_style.get()` returns the value passed to `chat_structured`. Pins the in-request propagation.

### `tests/test_cli.py` (new)
- Mock `agent.run_stream` and `review_response`.
- Assert generated tokens/prose are not printed before reviewer approval.
- Approved response → final prose displayed once and approved `chat_history`/`model_history` saved.
- Blocked response → only `REVIEW_BLOCKED_MESSAGE` displayed; generated prose/new model messages are not displayed or saved.

