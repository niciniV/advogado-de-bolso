# Implementation Plan (Revised v2) — Thin Index

> **Replaces** the previous 1416-line `revised-integration-plan.md`. The plan was split into 25 concern-grouped files (00-24) plus an index (99) in round 19 of the implementation-review-fix loop. This file is the thin landing page; the full content has moved to the sibling files below.

---

## Summary

This plan integrates a `base_frontend` React UI with a Python FastAPI backend for an agentic Brazilian consumer-rights chatbot (CDC / Lei 8.078/90). It introduces typed Pydantic tool return envelopes, per-case JSON persistence, an explicit SPA fallback route, reviewer-gated blocking with 422 envelopes, and a 20-step gated implementation order. 60 plan-level issues are closed; 0 are open. See `.opencode/loop/open-issues.md` for the full issue history and votes.

## Sibling files

The full content has moved to 25 concern-grouped files under `.opencode/plans/`. Each file has a 4-6 line header with related-sibling links. The canonical entry point is [`99-index.md`](./99-index.md).

| # | File | Summary |
|---|------|---------|
| 00 | [00-overview-and-architecture.md](./00-overview-and-architecture.md) | Title, "Replaces" note, and the 10-bullet Architecture Summary. |
| 01 | [01-contracts.md](./01-contracts.md) | `contracts.py` — `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` Pydantic envelopes. |
| 02 | [02-schemas.md](./02-schemas.md) | `schemas.py` — wire types for the API. |
| 03 | [03-adapter.md](./03-adapter.md) | `adapter.py` — `extract_structured_response` plus the three helpers. |
| 04 | [04-storage.md](./04-storage.md) | `storage/cases.py` — `Case` model, `load`/`save`/`delete`/`list_all`. |
| 05 | [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) | `agent.py` — `build_agent`, `STYLE_PROMPTS`, full merged `SYSTEM_PROMPT`. |
| 06 | [06-service-class.md](./06-service-class.md) | `service.py` `ChatService` class. |
| 07 | [07-service-helpers-and-backend.md](./07-service-helpers-and-backend.md) | `service.py` module-scope helpers + `AgentChatBackend`. |
| 08 | [08-api.md](./08-api.md) | `api.py` — endpoint list, SPA fallback, blocked-envelope 422. |
| 09 | [09-cli-config-deps.md](./09-cli-config-deps.md) | `cli.py`, `config.py` (`cases_path` env alias), `deps.py`. |
| 10 | [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) | `Makefile`, `package.json` rewrite, `vite.config.ts`, `package-lock.json`. |
| 11 | [11-frontend-types-and-defaults.md](./11-frontend-types-and-defaults.md) | `types.ts` + `defaults.ts`. |
| 12 | [12-frontend-api-client.md](./12-frontend-api-client.md) | `api.ts` — wire interfaces, mappers, `renameCase` wrapper. |
| 13 | [13-frontend-app.md](./13-frontend-app.md) | `App.tsx` (full rewrite) + `ChatInterface.tsx`. |
| 14 | [14-frontend-tests.md](./14-frontend-tests.md) | `api.test.ts` + `App.test.tsx`. |
| 15 | [15-backend-tests.md](./15-backend-tests.md) | All backend test-file specs. |
| 16 | [16-tools-modifications.md](./16-tools-modifications.md) | "Files to Modify" — `tools/*.py`. |
| 17 | [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) | "Files to Modify" — `config.py`, `.env.example`, `README.md`, `test_config.py`. |
| 18 | [18-frontend-modifications.md](./18-frontend-modifications.md) | "Files to Modify" — short pointer list for frontend. |
| 19 | [19-files-to-delete.md](./19-files-to-delete.md) | Files to Delete — `base_frontend/server.ts`. |
| 20 | [20-implementation-order.md](./20-implementation-order.md) | The 9-step gated implementation order. |
| 21 | [21-functional-checks.md](./21-functional-checks.md) | The 21 functional verification scenarios. |
| 22 | [22-resolved-decisions.md](./22-resolved-decisions.md) | "Resolved Open Decisions" #1 and #2. |
| 23 | [23-issue-tracking-table.md](./23-issue-tracking-table.md) | "Resolved Open Decisions" #3 — full ISSUE-* table. |
| 24 | [24-out-of-scope.md](./24-out-of-scope.md) | Out-of-Scope Notes. |

## Cross-reference policy

- All cross-references between files use **semantic anchors** (file path + section heading), not line numbers.
- Each file has a 4-6 line header that identifies the file, its purpose, and lists its 1-4 most relevant sibling files.
- The `Create` / `Modify` duplication in the source plan is resolved by placing the full spec once and using a one-line pointer in the duplicate location. No information is lost.

## Audit

See [`.opencode/loop/notes/split-manifest.md`](../loop/notes/split-manifest.md) for the audit table mapping each new file to its source-plan line range.
