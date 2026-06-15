# 21-functional-checks.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1307-1328)
**In this file:** The 21 functional verification scenarios (dev mode, UI smoke, persistence, CRUD, style switching, reviewer block, demo cases, production, CORS, CLI, SPA typo, retained-lock serialization, empty prose, unknown tool name, UUID case routes, history mapping, demo API isolation, quick-guide isolation).
**Related files:** [20-implementation-order.md](./20-implementation-order.md) (the gated batches that culminate in these functional checks), [00-overview-and-architecture.md](./00-overview-and-architecture.md) (the architectural claims these checks verify), [14-frontend-tests.md](./14-frontend-tests.md) (the App.test.tsx suite pins several of these scenarios at the test level).

### Functional checks
1. `uv run pytest` — all tests pass.
2. `uv run ruff check src/` and `uv run mypy src/` — clean.
3. `cd base_frontend && npm run lint` (tsc) — clean.
4. **Dev mode**: `uv run advogado-api` on :8000; `cd base_frontend && npm run dev` on :5173.
5. **UI smoke**: send "Comprei um celular online e me arrependi" → deadline card, CDC art. 49, quick replies. First message auto-creates the case with title="Celular comprado online" and icon_name="shopping_bag".
6. **Persistence**: create case, restart server, refresh → case still in list with history (and `model_history` is intact, so turn-2 follow-ups retain tool-call context per ISSUE-M3-001).
7. **CRUD**: PATCH (rename), DELETE, list, select — all reflect immediately.
8. **Style switching**: change `responseStyle` to `simples` → plainer prose. Verify the `_current_style` ContextVar is reset (no leakage between requests).
9. **Reviewer block**: temporarily block → API returns 422 with the full `StructuredChatResponse` envelope (`session_id`, unchanged `chat_history`, `blocked=true`, `blocked_message`); frontend `handleSendMessage` parses the body and shows `blocked_message` to the user. For an existing case, verify the rejected turn does not change persisted `chat_history` or `model_history`.
10. **Demo cases**: on first load, three demo cases appear with a "DEMO" badge. After the first real case is created, demo cases disappear from the list.
11. **Production**: `make frontend` then `uv run advogado-api` → React on :8000.
12. **CORS**: PATCH/DELETE work from Vite on :5173 (allow_methods includes `"PATCH"` per ISSUE-DS-004).
13. **CLI**: `uv run advogado` → spinner/live status works while generation and review run; generated prose appears only after reviewer approval. A blocked answer displays only the safe blocked message and writes no turn. Approved case files are written to `./storage/cases/` and visible from the UI.
14. **API typo**: `GET http://localhost:8000/api/chatt` → 404 (not 200 + HTML). Exact first-segment check per ISSUE-009.
15. **Retained lock serialization**: create a case, queue concurrent delete/recreate operations for the same UUID, and verify they all serialize on the same retained lock object; no old-lock/new-lock split is possible.
16. **Empty prose**: agent returns empty string → `step_title = "Análise inicial"`, `step_content = ""` (ISSUE-004).
17. **Unknown tool name**: tool returns content with an unexpected `tool_name` → logged at WARNING, not raised (ISSUE-DS-006).
18. **UUID case routes**: malformed IDs on GET/PATCH/DELETE/history return 422 before storage access.
19. **Frontend history mapping**: reload a persisted case containing deadline/template fields and verify all snake_case wire fields render correctly after mapping, including required `Case.timestamp` and `Case.lastMessage`.
20. **Demo API isolation**: select, rename, and delete each demo case and verify no request is made to `/api/cases/case-*`. Send a message while a demo is active and verify the request uses `session_id: null`, creates a real UUID case, and removes demos.
21. **Quick-guide isolation**: select a real persisted case, then start a HomeDashboard quick guide. Verify the outgoing request uses `session_id: null`, the new response becomes the active case, and the previously selected case remains unchanged.

