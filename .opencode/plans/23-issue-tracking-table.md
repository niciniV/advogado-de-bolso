# 23-issue-tracking-table.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1346-1403)
**In this file:** The full ISSUE-* / REVIEW-* / USR-* fix table from "Resolved Open Decisions #3" (round-3 plan-level fixes). Reference material for reviewers — documents which closed issue introduced which plan-level change.
**Related files:** [22-resolved-decisions.md](./22-resolved-decisions.md) (Decisions #1 and #2, the high-level design decisions), [`.opencode/loop/open-issues.md`](file:///C:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/.opencode/loop/open-issues.md) (the source of truth for issue status, votes, and round history).

### 3. Plan-level fixes applied (round 3 of the implementation-review-fix loop)
The following reviewer issues were applied directly to this plan. Each is referenced in the section it touches. See `.opencode/loop/open-issues.md` for full context.

| Issue | Fix |
|-------|-----|
| ISSUE-001 | `REACT_DIST` path uses 3 `.parent` calls (was 4). |
| ISSUE-002 | Renamed service-layer wrapper to `ChatResult` (was self-named `StructuredChatResponse`). |
| ISSUE-003 | Spec'd `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies` in adapter.py. |
| ISSUE-004 | Empty-prose fallback filters whitespace-only paragraphs. |
| ISSUE-005 | `cases.save()` calls `mkdir(parents=True, exist_ok=True)`. |
| ISSUE-006 | Added `tests/test_adapter.py` contract test for `tool_plain` raw-object round-trip. |
| ISSUE-008 | User/assistant messages use distinct timestamps. |
| ISSUE-009 | SPA fallback uses `first_segment in {"api", "assets"}`. |
| ISSUE-010 | CLI writes to `./storage/cases/` (same as API). |
| ISSUE-011 | Full merged `SYSTEM_PROMPT` provided (replaced bullet excerpts). |
| ISSUE-M3-001 | Added `model_history: list[ModelMessage]` to `Case`. |
| ISSUE-M3-002 | Spec'd `_collect_tool_returns` in service.py; `_to_model_messages` removed entirely (ISSUE-IND-003) because no caller materialized — `model_history` is always populated on `Case`. |
| ISSUE-M3-003 | Refactored `AgentChatBackend` shown without reviewer; `ChatService` runs reviewer exactly once. |
| ISSUE-M3-004 | Full `package.json` rewrite spec'd (dev/build/start/clean + dep removal). |
| ISSUE-M3-005 | `is_demo` documented as frontend-only marker. |
| ISSUE-M3-006 | `delete_case` acquires the per-case lock before deleting; locks are retained for the service lifetime to prevent an old-lock/new-lock concurrency split. |
| ISSUE-M3-007 | `response_style` semantics clarified: persisted as case default + per-request override. |
| ISSUE-M3-008 | `update_case_meta` wired into `PATCH /api/cases/{case_id}`. |
| ISSUE-M3-009 | Replaced line numbers with type/method references. |
| ISSUE-M3-010 | Adapter uses `isinstance(content, (list, tuple))`. |
| ISSUE-M3-011 | Dropped `TypeAdapter.validate_python` redundant call. |
| ISSUE-M3-012 | `SYSTEM_PROMPT` now treats an empty `search_knowledge_base` result as the no-results signal (updated again in round 17 per ISSUE-USR-017 to use `[]` rather than the previous `fonte="sistema"` sentinel). |
| ISSUE-M3-013 | `handleSaveCaseFromChat` is an explicit user-triggered metadata PATCH for an already-persisted real case; auto-create never triggers a redundant PATCH. |
| ISSUE-M3-014 | `cases_path` uses `Field(..., alias="CASES_PATH")`. |
| ISSUE-M3-015 | Error contract: API catches backend/save exceptions, returns 503. |
| ISSUE-M3-016 | Explicit "delete inline `seedCases`/`initialPreferences`" added to App.tsx section. |
| ISSUE-M3-017 | `isLoading` renamed to `isSendingMessage`; new `isLoadingCases`. |
| ISSUE-M3-018 | Ordered implementation with per-step `pytest` gate (now 21 steps after adding the CLI reviewer gate). |
| ISSUE-DS-001 | `_now()` defined at module scope. |
| ISSUE-DS-002 | Frontend `handleSendMessage` parses body and surfaces `blocked_message`. |
| ISSUE-DS-003 | `vite.config.ts` `server.proxy` fully spec'd. |
| ISSUE-DS-004 | CORS `allow_methods` includes `"PATCH"`. |
| ISSUE-DS-005 | Frontend uses `/api/chat/structured` with new body shape. |
| ISSUE-DS-006 | Adapter logs WARNING for unknown tool names. |
| ISSUE-DS-007 | `list_all()` scalability constraint in docstring + soft warning at 500+ files. |
| ISSUE-DS-008 | ContextVar scoping test added; single-task assumption documented. |
| ISSUE-USR-011 | `AgentRunResult` import path corrected from `pydantic_ai.tools` to `pydantic_ai` (top-level re-export). |
| ISSUE-USR-012 | `_current_style` imported from `.agent` into `service.py` (added to the import block before the local helper definitions). |
| ISSUE-USR-013 | `update_case_meta` now acquires the per-case `asyncio.Lock` around the load/validate/save body (mirroring `delete_case`); unique-temp atomic replacement prevents torn JSON, while cross-process API/CLI lost updates are explicitly unsupported. |
| ISSUE-USR-014 | `@types/node` kept in `devDependencies` (NOT removed); `vite.config.ts` spec retains the existing `path`/`__dirname`/`process.env` usage and the `server.proxy` config from DS-003. |
| ISSUE-USR-015 | `StructuredChatResponse` augmented with `updated_at: datetime` and `chat_history: list[ChatMessage]`. `chat_structured` populates both before returning. The "server returns the full chat history" claim is now backed by the schema. `WireResponse` alias from ISSUE-002 still type-checks. |
| ISSUE-USR-016 | Persistence test relaxed: asserts `ToolReturnPart.content` is a `dict` with matching field values (not `isinstance(_, DeadlineResult)`) after JSON round-trip. In-memory `tool_plain` test (line 995) still asserts `isinstance(_, DeadlineResult)`. |
| ISSUE-USR-017 | Kept the "Responda APENAS com o texto final" prompt in `redigir.py` (line 1076 aligned with Open Decision #1, line 1236). Empty RAG result is `[]` (not the previous sentinel `KnowledgeChunk(fonte="sistema", ...)`); `rag.py` spec (line 1139) and SYSTEM_PROMPT (line 369) updated to match. |
| REVIEW-001 | Removed lock cleanup on delete; retaining one lock per observed UUID prevents waiters on an old lock from racing operations on a replacement lock. |
| REVIEW-002 | Demo selection/rename/delete are frontend-only; non-UUID demo IDs never reach UUID-typed API routes. |
| REVIEW-003 | Corrected the "Posso..." regex so capture group 1 contains the complete question. |
| REVIEW-004 | Existing-case chat requests ignore `title`/`icon_name`; PATCH is the only metadata-update path. |
| REVIEW-005 | Fully specified `mapCaseSummary`/`mapCaseResponse` required `timestamp` and `lastMessage` fields plus deterministic demo-vs-real initial loading. |
| ISSUE-REVIEW-006 | Quick-guide sends now use an explicit `forceNewCase` option so asynchronous React state clearing cannot append to the previously active case. |
| ISSUE-REVIEW-007 | `StructuredChatRequest` and `UpdateCaseRequest` reuse the same constrained title/icon/style aliases; invalid auto-create metadata is rejected before persistence. |
| ISSUE-REVIEW-008 | Service example imports and backend annotations are strict Ruff/mypy-compatible, and the service/API batch now runs both gates. |
| ISSUE-REVIEW-009 | `ChatMessage` requires `id`, `sender`, `text`, and `timestamp`; only structured assistant-display fields are optional. |
| ISSUE-REVIEW-010 | Reviewer-blocked HTTP 422 contract is standardized on the full `StructuredChatResponse` envelope throughout the plan and tests. |

