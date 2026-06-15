# 99-index.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** Index/landing file for the round-19 split. Lists all 25 sibling files (00-24) with one-line summaries and links. This file is the canonical entry point for the implementation plan.
**Related files:** [00-overview-and-architecture.md](./00-overview-and-architecture.md) (architecture overview), [`/opencode/loop/notes/split-manifest.md`](../../loop/notes/split-manifest.md) (the audit table mapping each file to its source-plan line range).

# Implementation Plan — Split Index

This plan replaces the previous 1416-line `revised-integration-plan.md`. The plan is split into 25 concern-grouped files (00-24) plus this index (99). The original path is now a thin index (see `/opencode/plans/revised-integration-plan.md`).

The full content has moved to the sibling files below. The split preserves all source-plan content verbatim — no information loss, no paraphrasing, no editorial changes.

## Files

| # | File | Summary |
|---|------|---------|
| 00 | [00-overview-and-architecture.md](./00-overview-and-architecture.md) | Title, "Replaces" note, and the 10-bullet Architecture Summary. |
| 01 | [01-contracts.md](./01-contracts.md) | `contracts.py` — `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` Pydantic envelopes. |
| 02 | [02-schemas.md](./02-schemas.md) | `schemas.py` — wire types for the API (`StructuredChatRequest`/`Response`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest`). |
| 03 | [03-adapter.md](./03-adapter.md) | `adapter.py` — `extract_structured_response` plus the three helpers `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`. |
| 04 | [04-storage.md](./04-storage.md) | `storage/__init__.py` and `storage/cases.py` — `Case` model, `load`/`save`/`delete`/`list_all`, path containment, atomic writes, lock retention. |
| 05 | [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) | `agent.py` — `build_agent`, `STYLE_PROMPTS`, `_current_style` ContextVar, full merged `SYSTEM_PROMPT`. |
| 06 | [06-service-class.md](./06-service-class.md) | `service.py` `ChatService` class — `__init__`, `_get_case_lock`, `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history`; `REVIEW_BLOCKED_MESSAGE`; `_now`/`_now_ms`; `ChatResult`; `ChatBackend`/`ReviewerLike` Protocols. |
| 07 | [07-service-helpers-and-backend.md](./07-service-helpers-and-backend.md) | `service.py` module-scope helpers `_collect_tool_returns`, `_truncate_history_to_turns`; `_to_model_messages` removal note; `AgentChatBackend`; `build_chat_service`. |
| 08 | [08-api.md](./08-api.md) | `api.py` — endpoint list, UUID-typed path parameters, CORS, static serving / explicit SPA fallback, blocked-envelope 422 contract, 503 error handler. |
| 09 | [09-cli-config-deps.md](./09-cli-config-deps.md) | `cli.py` (reviewer-gated buffered streaming), `config.py` addition (`cases_path` env alias), `deps.py` "no changes" note. |
| 10 | [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) | `Makefile`, full `package.json` rewrite, `vite.config.ts` `server.proxy`, `package-lock.json` generation note. |
| 11 | [11-frontend-types-and-defaults.md](./11-frontend-types-and-defaults.md) | `base_frontend/src/types.ts` (`is_demo` addition) and `base_frontend/src/defaults.ts` (`initialPreferences` + `seedCases`). |
| 12 | [12-frontend-api-client.md](./12-frontend-api-client.md) | `base_frontend/src/api.ts` — wire interfaces, snake↔camel mappers, `renameCase` thin wrapper. |
| 13 | [13-frontend-app.md](./13-frontend-app.md) | `base_frontend/src/App.tsx` (full handler rewrite, explicit `seedCases`/`initialPreferences` deletion, `isSendingMessage` rename, `forceNewCase`) and `base_frontend/src/components/ChatInterface.tsx` (rename `isLoading` → `isSendingMessage`). |
| 14 | [14-frontend-tests.md](./14-frontend-tests.md) | `base_frontend/src/api.test.ts` (mapper unit tests) and `base_frontend/src/App.test.tsx` (RTL integration tests). |
| 15 | [15-backend-tests.md](./15-backend-tests.md) | All backend test-file specs — `test_adapter.py`, `test_storage.py`, `test_calculos.py`, `test_redigir.py`, `test_rag_tool.py`, `test_api.py`, `test_service.py`, `test_agent.py`, `test_cli.py`. |
| 16 | [16-tools-modifications.md](./16-tools-modifications.md) | "Files to Modify" — `tools/calculos.py`, `tools/redigir.py`, `tools/rag.py`. |
| 17 | [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) | "Files to Modify" — `config.py`, `.env.example`, `README.md`, `tests/test_config.py`. |
| 18 | [18-frontend-modifications.md](./18-frontend-modifications.md) | "Files to Modify" — short pointer list (agent.py, service.py, api.py, cli.py, test_*.py) referencing the corresponding "Create" files. |
| 19 | [19-files-to-delete.md](./19-files-to-delete.md) | Files to Delete — `base_frontend/server.ts`. |
| 20 | [20-implementation-order.md](./20-implementation-order.md) | The 9-step gated implementation order with per-step pytest/ruff/mypy gates. |
| 21 | [21-functional-checks.md](./21-functional-checks.md) | The 21 functional verification scenarios. |
| 22 | [22-resolved-decisions.md](./22-resolved-decisions.md) | "Resolved Open Decisions" — Decision #1 (`redigir_documento` envelope) and Decision #2 (PATCH only). |
| 23 | [23-issue-tracking-table.md](./23-issue-tracking-table.md) | The full ISSUE-* / REVIEW-* / USR-* fix table from "Resolved Open Decisions #3". |
| 24 | [24-out-of-scope.md](./24-out-of-scope.md) | Out-of-Scope Notes — multi-worker uvicorn, `_index.json`, auth, API streaming, cross-process writes, lock-registry lifetime, single-task ContextVar scoping, sub-agent LRU cache. |

## Cross-reference policy

- All cross-references between files use **semantic anchors** (file path + section heading), not line numbers.
- Each file has a 4-6 line header that identifies the file, its purpose, and lists its 1-4 most relevant sibling files in this set.
- The `Create` / `Modify` duplication in the source plan is resolved by placing the full spec once (in the concern-grouped file) and using a one-line pointer in the duplicate location. No information is lost.

## Audit

See [`.opencode/loop/notes/split-manifest.md`](../../loop/notes/split-manifest.md) for the audit table mapping each new file to its source-plan line range.

