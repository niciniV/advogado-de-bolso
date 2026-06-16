# Batch 7 Handoff — Frontend Integration

## Status: In Progress (manual implementation)

Working directory: `C:\Users\Vitor\Desktop\Vinicius\Projetos\advogado-de-bolso`

## What's done

| # | Batch | Commit | Gate | Status |
|---|-------|--------|------|--------|
| 1 | Typed tool contracts | `d7e3a2d` | pytest 103/103, ruff/mypy clean | ✅ done |
| 2 | Schema/adapter | `edcfa9f` | pytest 187/187, ruff/mypy clean | ✅ done |
| 3 | Storage | `984e74a` | pytest 216/216, ruff/mypy clean | ✅ done |
| 4 | Service/API | `dfad639` | 4 gates green: pytest 287/287, ruff, mypy | ✅ done |
| 5 | CLI | `50b6826` | pytest 306/306, ruff/mypy clean | ✅ done |
| 6 | Frontend deps | `826469a` | `npm install`/`lint`/`build` all green | ✅ done |
| 7 | Frontend integration | **uncommitted** | `npm run test` 15/15 ✅, `lint` ✅, `build` ❓ | 🟡 partial |
| 8 | Operations/docs (Makefile, README) | — | — | ⏳ pending |
| 9 | Final gate | — | — | ⏳ pending |

## Subagent failure mode

The general subagent was crashing consistently with this error:

```
NOT NULL constraint failed: session_message.seq
```

This is a system-level DB error in the subagent system — not a code error. After several retries for batch 7, the subagent kept failing. I switched to manual implementation.

The plan-reviewer-m3 subagent is also failing with the same error (it worked for the first 5 batches but started failing on batch 6 onwards). The plan-reviewer-mimo and plan-reviewer-deepseek subagents worked at first but the user reported their credits went to zero, so they were not used after batch 4.

## Batch 7 partial state (uncommitted)

`git status`:
```
 M base_frontend/src/App.tsx
 M base_frontend/src/components/ChatInterface.tsx
 M base_frontend/src/types.ts
?? base_frontend/src/api.test.ts
?? base_frontend/src/api.ts
?? base_frontend/src/defaults.ts
```

### What was changed manually:

1. **`base_frontend/src/types.ts`** — Added `is_demo?: boolean;` field to the `Case` interface.

2. **`base_frontend/src/defaults.ts`** (new) — `initialPreferences` and `seedCases` with `is_demo: true`. Three demo cases (`case-1`, `case-2`, `case-3`) with bundled chatHistory.

3. **`base_frontend/src/api.ts`** (new) — Full API client with:
   - `WireDeadlineResult`, `WireChatMessage`, `WireStructuredChatResponse`, `WireCaseSummary`, `WireCaseResponse`, `WireStructuredChatRequest`, `WireUpdateCaseRequest` interfaces
   - `mapDeadline`, `mapChatMessage`, `mapStructuredResponse`, `mapCaseSummary`, `mapCaseResponse` mappers
   - `formatCaseDate`, `deriveLastMessage`, `deriveTagText` helpers
   - `apiClient` object: `chatStructured`, `listCases`, `getCase`, `updateCaseMeta`, `renameCase`, `deleteCase`, `getHistory`

4. **`base_frontend/src/api.test.ts`** (new) — 15 mapper/API-client tests. **All passing** in `npm run test`.

5. **`base_frontend/src/App.tsx`** — Rewrote with:
   - `seedCases`/`initialPreferences` imported from `./defaults`
   - `useState<boolean>(true)` for `isLoadingCases`
   - On mount: `apiClient.listCases()`; show seedCases if no real cases
   - `isLoading` → `isSendingMessage` rename
   - `pendingBlockedCaseRef` for blocked-first-message retry
   - `handleSendMessage(text, options?: { forceNewCase?: boolean })` with the new precedence (forceNewCase/demo → pendingBlockedCase → real activeCaseId → null)
   - `handleStartConsultation(initialPrompt?)` with `forceNewCase: true`
   - `handleSelectCase`/`handleDeleteCase`/`handleRenameCase` branch on `is_demo`
   - `handleSaveCaseFromChat` PATCHes title/icon_name when active real case
   - `handleUpdatePreferences` PATCHes `response_style` when real case is active
   - `deriveCaseMeta(text)` pure helper for title/icon derivation
   - **Note**: I preserved most of the existing UI/JSX to keep this manual rewrite tractable. The structural changes (handlers, is_demo branching, new API integration) are complete. Lint passes.

6. **`base_frontend/src/components/ChatInterface.tsx`** — Renamed `isLoading` prop to `isSendingMessage` and updated all references.

## What's left for Batch 7

### Required (to complete the batch)

1. **Delete `base_frontend/server.ts`** — Per `.opencode/plans/19-files-to-delete.md`. The Express + `@google/genai` server is replaced by the FastAPI server. Currently the file is still on disk.

2. **Create `base_frontend/src/App.test.tsx`** — Per `.opencode/plans/14-frontend-tests.md`. The plan calls for Vitest + React Testing Library integration tests with `global.fetch` mocked. Test cases:
   - Selecting, renaming, and deleting a demo case makes no API request
   - Sending while a demo is active posts `session_id: null`, then removes demos after the successful real-case response
   - A successful first message synthesizes one complete real `Case` from the request metadata plus the structured response without issuing `GET /api/cases/{id}`
   - A blocked first-message `422` response renders `blocked_message`; the next ordinary send reuses the returned `session_id` and resends the original derived `title`, `icon_name`, and `response_style`
   - Starting a new consultation or selecting another case after a blocked first message clears the pending retry context
   - Starting a quick-guide consultation while a real case is active sends `session_id: null` with an empty base history and does not append to or mutate the previously active case (ISSUE-REVIEW-006)
   - Selecting, renaming, and deleting a real case calls the expected UUID endpoint

3. **Run all 3 batch 7 gates**:
   - `cd base_frontend && npm run test` (must pass)
   - `cd base_frontend && npm run lint` (must pass)
   - `cd base_frontend && npm run build` (must succeed)

4. **DOX updates**:
   - `base_frontend/AGENTS.md` — Update to reflect batch 7 completion
   - `AGENTS.md` (root) — Update File Map + Project Overview
   - `.opencode/loop/open-issues.md` — Append `## Implementation Notes → Batch 7` section

5. **Commit** the batch as something like `feat(batch7): frontend integration (api client + App rewrite + delete server.ts)`.

## Batch 8: Operations/docs

Per `.opencode/plans/20-implementation-order.md`:
- Add the `Makefile` (frontend, dev-api, dev-frontend, dev targets)
- Update `README.md` with production/dev commands, single-worker requirement, `<1000` case constraint, and API/CLI concurrent-write limitation
- Run every command in Functional Checks that does not require live model credentials

## Batch 9: Final gate

Run all of:
- `uv run pytest`
- `uv run ruff check src/ tests/`
- `uv run mypy src/`
- `cd base_frontend && npm ci`
- `cd base_frontend && npm run test`
- `cd base_frontend && npm run lint`
- `cd base_frontend && npm run build`

## Plan files for reference

All in `.opencode/plans/`:
- `11-frontend-types-and-defaults.md` — types.ts + defaults.ts spec
- `12-frontend-api-client.md` — api.ts spec
- `13-frontend-app.md` — App.tsx + ChatInterface.tsx spec
- `14-frontend-tests.md` — api.test.ts + App.test.tsx spec
- `19-files-to-delete.md` — server.ts deletion
- `20-implementation-order.md` — gated batch order
- `21-functional-checks.md` — 21 functional verification scenarios
- `22-resolved-decisions.md` — resolved decisions
- `23-issue-tracking-table.md` — full issue table
- `24-out-of-scope.md` — out-of-scope notes

## Recommended approach for the next session

1. **Re-test the subagent** first — a fresh opencode session may have a working subagent. The error `NOT NULL constraint failed: session_message.seq` may be transient.

2. **If subagents work**: Dispatch a single batch 7 implementer subagent with the full handoff context (everything above + the full plan spec). It should:
   - Run all 3 gates
   - Delete server.ts
   - Create App.test.tsx
   - Update DOX
   - Commit

3. **If subagents still broken**: Continue manually. The remaining work is:
   - Delete `base_frontend/server.ts` (just `Remove-Item`)
   - Run `npm run build` to confirm it succeeds
   - Create `App.test.tsx` (a fairly involved file — read `.opencode/plans/14-frontend-tests.md` carefully)
   - Update DOX files
   - Commit

4. **Reviewer for batch 7**: When batch 7 is complete, dispatch the **M3 reviewer only** (per user instruction). Do NOT use mimo or deepseek.

5. **Batches 8 and 9** can be dispatched as separate subagent tasks once batch 7 is committed.
