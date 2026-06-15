# Split Manifest

**Date:** 2026-06-15
**Loop round:** 20 (split-application stage)
**Author:** splitter subagent
**Status:** COMPLETE — 25 sibling files + thin-index replacement created. All 60 plan-level issues preserved verbatim.

This manifest maps each new file under `.opencode/plans/` to its source-plan line range (`revised-integration-plan.md` pre-split, 1416 lines) and provides a one-sentence summary. It is the audit table for the round-19 decomposition.

## Table of Contents

| # | Target file (relative to `.opencode/plans/`) | Source lines (pre-split) | One-sentence summary |
|---|---|---|---|
| 00 | `00-overview-and-architecture.md` | 1–22 | Title, "Replaces" note, and the 10-bullet Architecture Summary. |
| 01 | `01-contracts.md` | 25–66 | `contracts.py` — `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` Pydantic envelopes. |
| 02 | `02-schemas.md` | 67–87 | `schemas.py` — `StructuredChatRequest`/`Response`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest` wire types. |
| 03 | `03-adapter.md` | 88–267 | `adapter.py` — `extract_structured_response` plus the three helpers `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`. |
| 04 | `04-storage.md` | 269–286 | `storage/__init__.py` (empty) and `storage/cases.py` — `Case` model, `load`/`save`/`delete`/`list_all`, atomic writes, lock retention. |
| 05 | `05-agent-and-system-prompt.md` | 287–392 | `agent.py` — `build_agent`, `STYLE_PROMPTS`, `_current_style` ContextVar, full merged `SYSTEM_PROMPT`. |
| 06 | `06-service-class.md` | 394–805 | `service.py` `ChatService` class — `__init__`, `_get_case_lock`, `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history`; `REVIEW_BLOCKED_MESSAGE`; `_now`/`_now_ms`; `ChatResult`; `ChatBackend`/`ReviewerLike` Protocols. |
| 07 | `07-service-helpers-and-backend.md` | 808–927 | `service.py` module-scope helpers `_collect_tool_returns`, `_truncate_history_to_turns`; `_to_model_messages` removal note; `AgentChatBackend`; `build_chat_service`. |
| 08 | `08-api.md` | 929–996 | `api.py` — endpoint list, UUID-typed path parameters, CORS, static serving / explicit SPA fallback, blocked-envelope 422 contract, 503 error handler. |
| 09 | `09-cli-config-deps.md` | 998–1015 | `cli.py` (reviewer-gated buffered streaming), `config.py` (`cases_path` env alias), `deps.py` "no changes" note. |
| 10 | `10-frontend-build-and-config.md` | 1113–1127, 1145–1147, 1204–1238 | `Makefile`, `package.json` rewrite, `vite.config.ts` `server.proxy`, `package-lock.json` generation note. |
| 11 | `11-frontend-types-and-defaults.md` | 1141–1143, 1270–1282 | `types.ts` (`is_demo` addition) and `defaults.ts` (`initialPreferences` + `seedCases`). |
| 12 | `12-frontend-api-client.md` | 1129–1139 | `api.ts` — wire interfaces, snake↔camel mappers, `renameCase` thin wrapper. |
| 13 | `13-frontend-app.md` | 1240–1268, 1276–1277 | `App.tsx` (full rewrite, explicit `seedCases`/`initialPreferences` deletion, `isSendingMessage` rename, `forceNewCase`) and `ChatInterface.tsx` (rename `isLoading` → `isSendingMessage`). |
| 14 | `14-frontend-tests.md` | 1100–1111 | `api.test.ts` (mapper unit tests) and `App.test.tsx` (RTL integration tests). |
| 15 | `15-backend-tests.md` | 1017–1098 | All backend test-file specs — `test_adapter.py`, `test_storage.py`, `test_calculos.py`, `test_redigir.py`, `test_rag_tool.py`, `test_api.py`, `test_service.py`, `test_agent.py`, `test_cli.py`. |
| 16 | `16-tools-modifications.md` | 1153–1160 | "Files to Modify" — `tools/calculos.py`, `tools/redigir.py`, `tools/rag.py`. |
| 17 | `17-config-and-docs-modifications.md` | 1011–1012, 1174–1181, 1201–1202 | "Files to Modify" — `config.py`, `.env.example`, `README.md`, `test_config.py`. |
| 18 | `18-frontend-modifications.md` | 1149–1151, 1162–1199, 1283 | "Files to Modify" — short pointer list for frontend. |
| 19 | `19-files-to-delete.md` | 1286–1289 | Files to Delete — `base_frontend/server.ts`. |
| 20 | `20-implementation-order.md` | 1293–1305 | The 9-step gated implementation order. |
| 21 | `21-functional-checks.md` | 1307–1328 | The 21 functional verification scenarios. |
| 22 | `22-resolved-decisions.md` | 1332–1344 | "Resolved Open Decisions" #1 and #2. |
| 23 | `23-issue-tracking-table.md` | 1346–1403 | "Resolved Open Decisions" #3 — full ISSUE-* table. |
| 24 | `24-out-of-scope.md` | 1405–1416 | Out-of-Scope Notes. |
| 99 | `99-index.md` | (synthesized) | Index/landing file. Replaces the original plan as the canonical entry point. |
| _index_ | `revised-integration-plan.md` | (replaced with thin index, ~20 lines) | Thin-index replacement preserving the original path. |

## Splitter instructions addressed

- **mimo DEC-002** (line-count estimate off by ~3 lines for `06-service-class.md`): verified the actual source content for `06-service-class.md` covers source lines 394-805 (412 content lines). File constructed with ~412 source lines plus ~5-line header. Updated line-count estimate is plausible per the proposal's §6 Q3 acknowledgment. The header explicitly states "lines 394-805" with the correct line count.
- **mimo DEC-003** (`19-files-to-delete.md` should include a `**See also:**` pointer to `00-overview-and-architecture.md`): `19-files-to-delete.md` header now includes a `**See also:**` pointer to `00-overview-and-architecture.md` per this candidate instruction.
- **deepseek DEC-002** (3-line `package-lock.json` section at plan lines 1145-1147 not in any file's stated line range): `10-frontend-build-and-config.md` now includes source lines 1113-1127 (Makefile), 1145-1147 (package-lock.json generated section), and 1204-1238 (package.json + vite.config.ts). The 3-line package-lock.json content is fully present in the new file.

## Verification

- All 25 sibling files created under `.opencode/plans/`.
- Original source plan at `.opencode/plans/revised-integration-plan.md` replaced with thin-index.
- Thin-index preserves the original path (so root `AGENTS.md` line 29 reference and loop-state references stay valid).
- Each new file has a 4-6 line header that identifies the file, its purpose, and lists its 1-4 most relevant sibling files in the new set.
- Cross-references use semantic anchors (file path + section heading), not line numbers.
- No information loss: source plan content preserved verbatim. The `Create` / `Modify` duplication is resolved by placing the full spec once and using a one-line pointer in the duplicate location (`18-frontend-modifications.md` and `17-config-and-docs-modifications.md`).
