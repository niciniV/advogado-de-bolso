# `.opencode/` Documentation Index

This file is a child DOX that documents the contents of the `.opencode/` directory at the project root. The project's main DOX root is `AGENTS.md` at the repo root; this file is local to `.opencode/`.

## File Map

| Path | Purpose |
|------|---------|
| `AGENTS.md` | This file — child DOX for the `.opencode/` directory. |
| `plans/revised-integration-plan.md` | Active implementation plan (thin-index replacement; see Plan sub-entry below). |
| `plans/00-overview-and-architecture.md` | Plan file 00 — architecture overview. |
| `plans/01-contracts.md` | Plan file 01 — `contracts.py` spec. |
| `plans/02-schemas.md` | Plan file 02 — `schemas.py` spec. |
| `plans/03-adapter.md` | Plan file 03 — `adapter.py` spec. |
| `plans/04-storage.md` | Plan file 04 — `storage/cases.py` spec. |
| `plans/05-agent-and-system-prompt.md` | Plan file 05 — `agent.py` spec. |
| `plans/06-service-class.md` | Plan file 06 — `ChatService` class spec. |
| `plans/07-service-helpers-and-backend.md` | Plan file 07 — service helpers + `AgentChatBackend`. |
| `plans/08-api.md` | Plan file 08 — `api.py` spec. |
| `plans/09-cli-config-deps.md` | Plan file 09 — `cli.py`, `config.py`, `deps.py` specs. |
| `plans/10-frontend-build-and-config.md` | Plan file 10 — `Makefile`, `package.json`, `vite.config.ts` specs. |
| `plans/11-frontend-types-and-defaults.md` | Plan file 11 — `types.ts` and `defaults.ts` specs. |
| `plans/12-frontend-api-client.md` | Plan file 12 — `api.ts` spec. |
| `plans/13-frontend-app.md` | Plan file 13 — `App.tsx` and `ChatInterface.tsx` specs. |
| `plans/14-frontend-tests.md` | Plan file 14 — frontend test specs. |
| `plans/15-backend-tests.md` | Plan file 15 — backend test specs. |
| `plans/16-tools-modifications.md` | Plan file 16 — tools `Files to Modify` specs. |
| `plans/17-config-and-docs-modifications.md` | Plan file 17 — config/docs `Files to Modify` specs. |
| `plans/18-frontend-modifications.md` | Plan file 18 — frontend `Files to Modify` pointer list. |
| `plans/19-files-to-delete.md` | Plan file 19 — `Files to Delete`. |
| `plans/20-implementation-order.md` | Plan file 20 — gated implementation order. |
| `plans/21-functional-checks.md` | Plan file 21 — functional verification scenarios. |
| `plans/22-resolved-decisions.md` | Plan file 22 — Resolved Open Decisions #1, #2. |
| `plans/23-issue-tracking-table.md` | Plan file 23 — Resolved Open Decisions #3 (ISSUE-* table). |
| `plans/24-out-of-scope.md` | Plan file 24 — Out-of-Scope Notes. |
| `plans/99-index.md` | Plan file 99 — index/landing file (canonical entry point). |
| `loop/notes/split-manifest.md` | Audit table mapping each plan file to its source-plan line range. |
| `loop/decomposition-proposal.md` | The round-19 decomposition proposal that drove the split. |
| `loop/open-issues.md` | Source of truth for all issues found during the implementation-review-fix loop. |
| `loop/orchestration-state.md` | Compact orchestration state for the implementation-review-fix loop. |
| `loop/fix-log.md` | Compact chronological log of fixer subagent activities. |
| `agents/plan-reviewer-nex.md` | Nex N2 Pro subagent for reviewing plans, designs, and code. |
| `agents/code-writer-nex.md` | Nex N2 Pro subagent for implementing focused code changes. |

## Plan

- **Active implementation plan**: `.opencode/plans/revised-integration-plan.md` (thin-index replacement of the original 1416-line plan).
- **The plan is split into 25 topic files** under `.opencode/plans/` (numbered 00-24) plus an index file (`99-index.md`). Each topic file is 10-420 lines, self-contained, and cross-references its 1-4 most relevant siblings. The canonical entry point is `99-index.md`. See `.opencode/loop/notes/split-manifest.md` for the audit table.

## Cross-references

- The root `AGENTS.md` File Map at the repo root references `.opencode/plans/revised-integration-plan.md` as the "Active implementation plan" (line 29 of root `AGENTS.md`). This thin-index file preserves that path; the actual plan content lives in the 25 sibling files.
- The `loop/` subdirectory contains the implementation-review-fix loop state (issues, fix log, orchestration state). See `.opencode/loop/open-issues.md` for the canonical issue tracker.
