# 14-frontend-tests.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1100-1111)
**In this file:** `base_frontend/src/api.test.ts` (mapper unit tests) and `base_frontend/src/App.test.tsx` (RTL integration tests for demo/quick-guide/blocked flows).
**Related files:** [12-frontend-api-client.md](./12-frontend-api-client.md) (the mappers the `api.test.ts` covers), [13-frontend-app.md](./13-frontend-app.md) (the handlers the `App.test.tsx` exercises), [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) (the Vitest + jsdom + RTL dependencies that make these tests runnable).

### `base_frontend/src/api.test.ts` (new)
- Use Vitest to test the pure wire mappers without rendering React.
- Assert `mapChatMessage` maps every snake_case nested field, including deadline dates/base/note.
- Assert `mapStructuredResponse` maps the complete returned history.
- Assert `mapCaseSummary` and `mapCaseResponse` always populate required `timestamp`, `date`, `lastMessage`, `iconName`, `responseStyle`, and `chatHistory`.

### `base_frontend/src/App.test.tsx` (new)
- Use Vitest + React Testing Library with `global.fetch` mocked.
- Selecting, renaming, and deleting a demo case makes no API request.
- Sending while a demo is active posts `session_id: null`, then removes demos after the successful real-case response.
- A blocked `422` response renders `blocked_message`; the next send reuses the returned `session_id`.
- Starting a quick-guide consultation while a real case is active sends `session_id: null` with an empty base history and does not append to or mutate the previously active case (ISSUE-REVIEW-006).
- Selecting, renaming, and deleting a real case calls the expected UUID endpoint.

