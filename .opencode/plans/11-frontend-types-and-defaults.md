# 11-frontend-types-and-defaults.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1141-1143 + 1270-1282)
**In this file:** Frontend types and seed data — `base_frontend/src/types.ts` (`is_demo` addition) and `base_frontend/src/defaults.ts` (`initialPreferences` + `seedCases` with `is_demo: true`).
**Related files:** [02-schemas.md](./02-schemas.md) (the snake_case wire types that `types.ts` mirrors), [12-frontend-api-client.md](./12-frontend-api-client.md) (the `mapCaseSummary`/`mapCaseResponse` mappers that translate wire types to these UI types), [13-frontend-app.md](./13-frontend-app.md) (the `App.tsx` handlers that branch on `is_demo`).

### `base_frontend/src/defaults.ts` (new)
- `initialPreferences` (moved from `App.tsx`).
- `seedCases: Case[]` — the three demo cases, each with `is_demo: true` and a `tagText: "DEMO"`.

### `base_frontend/src/types.ts`
- Add `is_demo?: boolean` to `Case` (ISSUE-M3-005). Frontend-only marker.
- `iconName` union unchanged (4 hardcoded values).
- `date: string` stays — client-derived by the mapper.
- Keep `tagText` and `date` only on `Case`; do not add them to `ChatMessage`.

### `base_frontend/src/defaults.ts` (new, additional spec)
- `initialPreferences` (moved from `App.tsx` lines 132-144).
- `seedCases: Case[]` — the three demo cases, each with `is_demo: true` and a `tagText: "DEMO"`. These are the **only** `is_demo: true` cases in the system. The server never produces one.
- Demo IDs remain the existing readable non-UUID values (`case-1`, `case-2`, `case-3`) to make their frontend-only status obvious. App handlers MUST branch on `is_demo` before invoking any API client method.

