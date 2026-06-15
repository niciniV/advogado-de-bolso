# 13-frontend-app.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1240-1268 + 1276-1277)
**In this file:** `base_frontend/src/App.tsx` spec (full handler rewrite, explicit `seedCases`/`initialPreferences` deletion, `isSendingMessage` rename, `forceNewCase`) and `base_frontend/src/components/ChatInterface.tsx` (rename `isLoading` → `isSendingMessage`).
**Related files:** [11-frontend-types-and-defaults.md](./11-frontend-types-and-defaults.md) (the `seedCases`/`initialPreferences` now imported from `defaults.ts`), [12-frontend-api-client.md](./12-frontend-api-client.md) (the `apiClient` methods called by these handlers), [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) (the Vite proxy that `handleSendMessage` reaches in dev).

### `base_frontend/src/App.tsx`
ISSUE-M3-016: explicitly **delete** the inline `seedCases` (lines 20-130, ~110 lines) and `initialPreferences` (lines 132-144). The plan said "move to `defaults.ts`" but the deletion must be explicit. After the move, `App.tsx` imports them:
```ts
import { seedCases, initialPreferences } from "./defaults";
```
- The `is_demo: true` flag on each seed case stays frontend-only (ISSUE-M3-005). The server never sets `is_demo: true`. `CaseSummary.is_demo` is reserved for future server-side template cases and is not used today.
- Add `useState<boolean>(true)` for `isLoadingCases` (ISSUE-M3-017). On mount, call `apiClient.listCases()`. While loading, show a spinner. When loading succeeds, render mapped real cases if any exist; otherwise render `seedCases`. This prevents an empty server response from accidentally removing the demos before the first real case is created.
- **Rename** the existing `isLoading` (per-message chat spinner) to `isSendingMessage` (ISSUE-M3-017). Update `ChatInterface` props to use `isSendingMessage`. The two loading flags now have unambiguous names.
- `handleSendMessage`:
  - Change the signature to `handleSendMessage(text, options?: { forceNewCase?: boolean })`. When `forceNewCase === true`, derive the request from an explicit empty conversation snapshot, ignore/clear any pending blocked-case retry ID, and send `session_id: null` regardless of the currently-rendered `activeCaseId`/`currentChatHistory`. Do not rely on preceding `setActiveCaseId(null)` or `setCurrentChatHistory([])` calls being visible synchronously; React state updates are asynchronous (ISSUE-REVIEW-006).
  - If `activeCaseId === null`, this is the first message of a new case. Compute `title` and `icon_name` from the message text (current keyword logic from `App.tsx:296-340`). Send `{message, session_id: null, response_style, title, icon_name}` to `POST /api/chat/structured` (ISSUE-DS-005: NOT `/api/chat`, which is deleted).
  - If the active case is a demo, treat the send as the first message of a **new real case**: clear the demo history from the active conversation, compute title/icon from the new message, and send `session_id: null`. Never send the demo's non-UUID ID. On success, replace the active demo with the newly-created real case response.
  - On response, use `mapStructuredResponse`; set `activeCaseId = mapped.sessionId` and replace `currentChatHistory` with `mapped.chatHistory`. Derive case-level `date`/`tagText` separately when updating the local case list.
  - **Error handling** (ISSUE-DS-002 + ISSUE-USR-004): if `!response.ok`, parse the body. If `body.blocked === true`, display `body.blocked_message` to the user via the chat (not a generic error). Capture `body.session_id` from the 422 body if present, store it in a ref (e.g., `pendingBlockedCaseIdRef`), and — on the next send — reuse it as the `session_id` for the retry. This avoids orphan cases on blocked first messages (the server already skipped `cases.save` for blocked-new-case per ISSUE-USR-004, but if any old code path persists the blocked case, the client must still pin the id to prevent duplicates).
- `handleStartConsultation(initialPrompt?)`: clear the visible selection/history as today. If `initialPrompt` is present (the quick-guide path), call `handleSendMessage(initialPrompt, { forceNewCase: true })`. This explicit option prevents the immediate call from closing over the previously active case before React commits the clearing state updates.
- `handleSaveCaseFromChat`:
  - This is the explicit user-triggered "save this generated result" action from the tool card. It does not create cases because the first successful message already auto-created one.
  - If there is no active case or the active case is a demo, return without an API call.
  - Derive `title` and `icon_name` from the first user message using the same pure `deriveCaseMeta(text)` helper used by first-message auto-create. Send exactly one `updateCaseMeta(activeCaseId, { title, icon_name })` PATCH and merge the returned `CaseResponse` into local state.
  - `response_style` is not sent by this handler. `handleUpdatePreferences` PATCHes `{ response_style }` when a real case is active; otherwise the selected preference is sent with the next first-message request and becomes the new case default.
  - The first-message auto-create flow MUST NOT call this handler automatically; its title/icon are already in the structured chat request.
- `handleSelectCase`: if the selected case has `is_demo === true`, load its bundled `chatHistory` locally and do **not** call the API. Otherwise call `apiClient.getCase(caseId)`.
- `handleDeleteCase`: if the selected case has `is_demo === true`, remove it from local state only. Otherwise call `apiClient.deleteCase(caseId)`.
- `handleRenameCase`: if the selected case has `is_demo === true`, rename it in local state only. Otherwise call `apiClient.renameCase(caseId, newTitle)`, which under the hood calls `apiClient.updateCaseMeta(caseId, { title: newTitle })` and issues `PATCH /api/cases/{case_id}` with `{ title }` (ISSUE-IND-002). There is no dedicated `renameCase` REST endpoint; the frontend rename is a PATCH with a `{ title }` body.
- Demo IDs such as `"case-1"` are never passed to `chatStructured`, `getCase`, `updateCaseMeta`, `renameCase`, `deleteCase`, or `getHistory`; all API case IDs remain UUIDs.
- The `history` field in the request body is removed (server is now the source of truth; the server returns the full snake_case chat history with each response, and `mapChatMessage` converts every item before it reaches React state).
- Filter out `is_demo` cases when the first real case is created (clear them from local state, never re-add during that app session). A later full reload shows demos only if `listCases()` again returns no real cases.
- Extract the current title/icon keyword logic into pure `deriveCaseMeta(text): { title: string; icon_name: IconName }`; both first-message auto-create and `handleSaveCaseFromChat` call it, preventing metadata drift.
- `handleUpdatePreferences`: update local preferences immediately. If a real case is active and `responseStyle` changed, call `updateCaseMeta(activeCaseId, { response_style: updated.responseStyle })`; never PATCH demos or an unsaved/new conversation.

### `base_frontend/src/components/ChatInterface.tsx`
Rename the `isLoading` prop to `isSendingMessage` and update all message-submission conditions and disabled states. Case-list loading remains owned by `App.tsx`.

