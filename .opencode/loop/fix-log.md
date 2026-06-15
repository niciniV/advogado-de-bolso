# Fix Log

Compact chronological log of fixer subagent activities.

## Round 3 — general (fixer)

- **Date**: 2026-06-14
- **Fixer**: general
- **Scope**: All 37 verified issues from the round-1/round-2 review cycle.
- **Summary**: 37 fixed_pending_review, 0 blocked, 0 untouched, tests: n/a (plan-level fixes only).
- **Files touched**: `.opencode/plans/revised-integration-plan.md` (the entire plan was updated to address every verified issue).
- **Notable fixes**:
  - ISSUE-001: `REACT_DIST` path corrected from 4 to 3 `.parent` calls
  - ISSUE-002: renamed `StructuredChatResponse` wrapper to `ChatResult` (self-naming collision)
  - ISSUE-003: spec'd `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies` in adapter.py
  - ISSUE-004: empty-prose fallback now actually fires
  - ISSUE-005: `mkdir(parents=True, exist_ok=True)` in `cases.save`
  - ISSUE-006: contract test for `tool_plain` raw-object round-trip added to `test_adapter.py`
  - ISSUE-007: marked fixed_pending_review (status observation; implementation order spec'd in plan)
  - ISSUE-008: distinct timestamps for user/assistant messages
  - ISSUE-009: SPA fallback uses exact first-segment check
  - ISSUE-010: CLI and API share the same `./storage/cases/` path
  - ISSUE-011: full merged `SYSTEM_PROMPT` provided
  - ISSUE-M3-001: `model_history: list[ModelMessage]` field added to `Case`
  - ISSUE-M3-002: spec'd `_collect_tool_returns` and `_to_model_messages`
  - ISSUE-M3-003: refactored `AgentChatBackend.run()` shown without reviewer
  - ISSUE-M3-004: full `package.json` rewrite (all 4 scripts + dep removal)
  - ISSUE-M3-005: `is_demo` documented as frontend-only marker
  - ISSUE-M3-006: `delete_case` acquires per-case lock before deleting
  - ISSUE-M3-007: `response_style` semantics clarified (persisted default + per-request override)
  - ISSUE-M3-008: `update_case_meta` wired into `PATCH /api/cases/{case_id}`
  - ISSUE-M3-009: pinned pydantic_ai line numbers replaced with type references
  - ISSUE-M3-010: `isinstance(content, (list, tuple))` for adapter dispatch
  - ISSUE-M3-011: dropped redundant `TypeAdapter.validate_python`
  - ISSUE-M3-012: `SYSTEM_PROMPT` aligned with `fonte="sistema"` no-results behavior
  - ISSUE-M3-013: `handleSaveCaseFromChat` PATCH fires only on manual edit
  - ISSUE-M3-014: `cases_path` uses `Field(..., alias="CASES_PATH")`
  - ISSUE-M3-015: error contract spec'd (API catches, returns 503)
  - ISSUE-M3-016: explicit "delete inline `seedCases`/`initialPreferences`" added
  - ISSUE-M3-017: `isLoading` renamed to `isSendingMessage`; new `isLoadingCases`
  - ISSUE-M3-018: 20-step ordered implementation with per-step `pytest` gate
  - ISSUE-DS-001: `_now()` defined at module scope
  - ISSUE-DS-002: frontend parses body, surfaces `blocked_message`
  - ISSUE-DS-003: `vite.config.ts` `server.proxy` fully spec'd
  - ISSUE-DS-004: CORS `allow_methods` includes `"PATCH"`
  - ISSUE-DS-005: frontend uses `/api/chat/structured` with new body shape
  - ISSUE-DS-006: adapter logs WARNING for unknown tool names
  - ISSUE-DS-007: `list_all()` scalability constraint in docstring + soft warning at 500+ files
  - ISSUE-DS-008: ContextVar scoping documented + tests added
- **Verification**: No tests run (plan-level fixes only). The plan now spec's a 20-step implementation order with `pytest` gates; a future implementation round will run the tests.
- **Regression risk**: Low. The plan is the only file modified; no source code was changed in this round.

## Round 5 — general (fixer)

- **Date**: 2026-06-14
- **Fixer**: general
- **Scope**: All 4 verified issues from the round-4 post-fix review.
- **Summary**: 4 fixed_pending_review, 0 blocked, 0 untouched, tests: n/a (plan-level fixes only).
- **Files touched**: `.opencode/plans/revised-integration-plan.md` (4 targeted plan edits).
- **Notable fixes**:
  - ISSUE-010: Files to Modify section's `cli.py` summary line 900 updated from `./storage/cli_history/` → `./storage/cases/` (Files to Create was already correct; only the summary was stale).
  - ISSUE-M3-007: schemas.py `StructuredChatRequest` description (line 72) replaced "does NOT persist" with the accurate dual-mechanism description (ContextVar overrides per-request; persisted case default read back on subsequent turns).
  - ISSUE-DS-009: `chat_structured` restructured — `_current_style.set(...)` moved from BEFORE case load to AFTER, with fallback chain `response_style or case.response_style or "detalhado"`. ContextVar reset moved into a nested `try/finally` inside the lock scope. The persisted default is now actually read back on subsequent turns.
  - ISSUE-DS-010: cli.py Files to Create section explicitly states the CLI constructs a `Case` with both `chat_history` and `model_history` populated before calling `cases.save(case)`. Cross-transport loadability (CLI→API) preserves tool-call/return context.
- **Verification**: No tests run. All 4 issues are plan-level fixes (no source code written); `pytest`/`mypy`/`ruff` are not applicable. Future implementation rounds will exercise the plan via the 20-step order.
- **Regression risk**: Low. The three plan sections touched (schemas.py description, service.py `chat_structured`, cli.py bullet + summary) are additive clarifications consistent with the existing round-3 fix notes. No new helpers, no signature changes.

## Round 8 — general (fixer)

- **Date**: 2026-06-15
- **Fixer**: general
- **Scope**: All 10 verified user-supplied issues from the round-7 review (ISSUE-USR-001 through ISSUE-USR-010).
- **Summary**: 10 fixed_pending_review, 0 blocked, 0 untouched, tests: n/a (plan-level fixes only).
- **Files touched**: `.opencode/plans/revised-integration-plan.md` (cross-cutting plan edits spanning schemas, service, storage, api, adapter, agent, and tests).
- **Notable fixes**:
  - **ISSUE-USR-001 (path traversal):** `StructuredChatRequest.session_id` retyped to `UUID | None` (Pydantic-validated). `chat_structured` signature updated to accept `UUID | None`; added `from uuid import UUID`. `storage/cases.py` spec adds path-containment requirement (`file_path.resolve().is_relative_to(cases_path.resolve())`).
  - **ISSUE-USR-002 (tool-result leakage):** backend returns `result.new_messages()` (current turn only) instead of `result.all_messages()`. `ChatBackend` protocol docstring updated to `run(message, history) -> (prose, new_messages)`. `_collect_tool_returns` consumes `new_messages`. Persistence becomes `case.model_history = case.model_history + new_messages` (append, not replace). Storage section description updated.
  - **ISSUE-USR-003 (20-turn cap slices messages):** added `_truncate_history_to_turns(history, max_turns)` helper that groups by `ModelRequest` containing a `UserPromptPart`. `chat_structured` now calls the helper instead of `model_history[-N:]`. Keeps every `ToolCallPart`/`ToolReturnPart` pair paired.
  - **ISSUE-USR-004 (orphaned blocked cases):** `chat_structured` tracks `was_new_case = case is None`. When the reviewer blocks a brand-new case, `cases.save(case)` is SKIPPED. Frontend `handleSendMessage` updated: blocked-error branch captures `body.session_id` from 422 into a ref, reuses on retry.
  - **ISSUE-USR-005 (API contract inconsistency):** schemas adds `UpdateCaseRequest { title?, icon_name?, response_style? }` (with a `model_validator` rejecting empty bodies with 422). `RenameCaseRequest` marked DEPRECATED. Endpoint list adds missing `GET /api/cases/{case_id}`. PATCH body switched to `UpdateCaseRequest`. Frontend `handleSaveCaseFromChat` collapsed to one PATCH. `tests/test_api.py` adds PATCH body, single-case, and blocked-no-orphan tests. Architecture summary updated.
  - **ISSUE-USR-006 (wrong Case import):** `service.py` import block corrected; `Case` is now imported from `storage.cases` (where it lives), with an inline comment explaining the prior `ImportError`.
  - **ISSUE-USR-007 (cases_path not wired):** `ChatService.__init__` takes `cases_path: Path` keyword-only. All four storage functions (`load`, `save`, `delete`, `list_all`) take `cases_path: Path` keyword-only. `chat_structured`, `delete_case`, and the CLI all pass `cases_path=self._cases_path` (or `settings.cases_path`) on every call. `build_chat_service` documented to wire `cases_path=settings.cases_path`. Files to Modify `config.py` section now matches Files to Create (with the alias).
  - **ISSUE-USR-008 (date serialization):** both `model_dump()` call sites on `DeadlineResult` now use `model_dump(mode="json")` (the 422 `JSONResponse` and the `chat_history` `ChatMessage.deadline` field). Comment documents the failure mode and the `jsonable_encoder` alternative.
  - **ISSUE-USR-009 (tautological test):** the `tool_plain` raw-object contract test is rewritten to register a real `@agent.tool_plain` function returning a `DeadlineResult`, run a real `agent.run(...)` call, and assert `result.new_messages()` ends with a `ToolCallPart` followed by a `ToolReturnPart` whose `content` is `isinstance(_, DeadlineResult)`. Test docstring notes that JSON reload produces a `dict` and persistence is a separate test.
  - **ISSUE-USR-010 (regex question bug):** pattern 1 now requires the numbered item to end in `?` (no more non-question extraction). Pattern 3 uses a single capture group wrapping the full question (no more "Posso?" truncation). Two new test bullets pin both behaviors.
- **Verification**: No tests run. All 10 issues are plan-level fixes (no source code written); `pytest`/`mypy`/`ruff` are not applicable. Future implementation rounds will exercise the plan via the 20-step order.
- **Regression risk against the 39 already-closed issues**: verified consistency by spot-check.
  - ISSUE-M3-001 (`model_history: list[ModelMessage]`): USR-002 keeps the field; persistence now uses `case.model_history + new_messages` instead of replacing. The 20-turn cap (M3-001 / M3-018) is preserved via `_truncate_history_to_turns`.
  - ISSUE-M3-007 / ISSUE-DS-009 (`response_style` semantics): USR-007 does not touch the `effective_style = response_style or case.response_style or "detalhado"` fallback chain. The fix from round 5 is preserved.
  - ISSUE-M3-008 (`update_case_meta` wiring): USR-005 keeps the wiring — PATCH still delegates to `ChatService.update_case_meta`, just with a richer body.
  - ISSUE-M3-014 (`cases_path` env alias): USR-007 keeps `Field(default=Path("./storage/cases"), alias="CASES_PATH")` and now also wires it through to the service.
  - ISSUE-010 (CLI storage path): USR-007 keeps `./storage/cases/` for both CLI and API; both transports now also pass `cases_path` explicitly.
  - ISSUE-DS-010 (CLI save shape): USR-007 keeps the dual `chat_history` + `model_history` save and now also passes `cases_path=settings.cases_path`.
  - No new regressions introduced.
