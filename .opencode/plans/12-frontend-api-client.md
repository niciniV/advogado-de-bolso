# 12-frontend-api-client.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1129-1139)
**In this file:** `base_frontend/src/api.ts` spec — wire interfaces, snake↔camel mappers, `renameCase` thin wrapper.
**Related files:** [02-schemas.md](./02-schemas.md) (the snake_case wire types the mappers consume), [11-frontend-types-and-defaults.md](./11-frontend-types-and-defaults.md) (the camelCase UI types the mappers produce), [08-api.md](./08-api.md) (the HTTP endpoints each method hits).

### `base_frontend/src/api.ts` (new)
Thin HTTP client + snake↔camel mapper:
- Define explicit snake_case wire interfaces for `WireDeadlineResult`, `WireChatMessage`, `WireStructuredChatResponse`, `WireCaseSummary`, and `WireCaseResponse`. Do not cast API JSON directly to UI types.
- `mapDeadline(payload): Deadline` — maps `data_inicio → startDate`, `data_limite → endDate`, `base_legal → base`, `nota → note`, derives `title = "Prazo calculado"`, and derives a user-facing `type` from `item_label` or `tipo_prazo`.
- `mapChatMessage(payload): ChatMessage` — maps every snake_case nested field (`step_title`, `relevant_content`, `suggestive_text`, `template_letter`, `quick_replies`, and `deadline`) to the camelCase UI shape.
- `mapStructuredResponse(payload): { sessionId: string; updatedAt: string; chatHistory: ChatMessage[] }` — maps the full server-returned history. It does **not** set `tagText` or `date`, because those fields belong to `Case`, not `ChatMessage`.
- `mapCaseSummary(payload): Case` — maps summary metadata, derives `date` from `updated_at` ("Hoje" | "Ontem" | "DD MMM"), sets `timestamp = Date.parse(updated_at)`, maps `lastMessage = last_message`, derives `tagText` from the server summary, and initializes `chatHistory: []`.
- `mapCaseResponse(payload): Case` — maps the complete selected-case metadata and every history item with `mapChatMessage`; sets `timestamp = Date.parse(updated_at)`, derives `date` from `updated_at`, and derives required `lastMessage` from the last assistant message's `stepContent || text` (falling back to `""` when no assistant message exists). `tagText` is derived from the last assistant message: deadline → `"Prazo calculado"`, template letter → `"Mensagem pronta"`, otherwise `undefined`.
- `chatStructured`, `listCases`, `getCase`, `renameCase`, `deleteCase`, `getHistory`.
- `renameCase(caseId, newTitle)` (ISSUE-IND-002) is a **thin wrapper** around `updateCaseMeta(caseId, { title: newTitle })`: it PATCHes `/api/cases/{case_id}` with `{ title: newTitle }` and the server-side `update_case_meta` does the work. There is no dedicated `renameCase` REST endpoint; the PATCH is the single metadata-update surface. `handleRenameCase` in `App.tsx` calls this wrapper.
- API-client methods accept server UUIDs only. Demo cases are intercepted by `App.tsx` before any API-client method is invoked.

