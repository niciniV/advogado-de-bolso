# 18-frontend-modifications.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1149-1151 + 1162-1199 + 1283)
**In this file:** "Files to Modify" — short pointer list (agent.py, service.py, api.py, cli.py, test_*.py — all reference the corresponding "Create" file in items 6-16). The few items with new content beyond the Create file are folded into the related concern files (`10`–`15`).
**Related files:** [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) (the `agent.py` rewrite, the full source spec), [06-service-class.md](./06-service-class.md) (the `service.py` rewrite), [08-api.md](./08-api.md) (the `api.py` rewrite), [09-cli-config-deps.md](./09-cli-config-deps.md) (the `cli.py` rewrite), [15-backend-tests.md](./15-backend-tests.md) (the test rewrites).

### `src/advogado_de_bolso/agent.py`
See "Files to Create" section above. Add `@agent.instructions` callback. Update `SYSTEM_PROMPT` to describe the new tool return shapes. Add `STYLE_PROMPTS` and `_current_style` ContextVar.

### `src/advogado_de_bolso/service.py`
See "Files to Create" section above. Drop `chat`, `clear_session`, `session_history`, `session_count`, `_max_sessions`, `_evict_old_sessions`, `_max_history_messages`. Add `chat_structured`, `list_cases`, `get_case`, `update_case_meta`, `delete_case`, `get_history` (`rename_case` removed per ISSUE-IND-002 — the PATCH endpoint delegates to `update_case_meta`, and a single-field rename is just `update_case_meta(case_id, title=new_title)`). Add the retained per-case `asyncio.Lock` registry and the `ChatResult` dataclass wrapper (replacing `ChatReply`). Apply the 20-turn cap only to LLM-bound history.

### `src/advogado_de_bolso/api.py`
See "Files to Create" section above. Drop the old endpoints. Add the new ones. Use explicit SPA fallback. Return 422 for blocked.

### `src/advogado_de_bolso/cli.py`
See "Files to Create" section above. Keep `agent.run_stream`, but buffer generated prose until `review_response()` approves it. Preserve spinner/live status, not token-by-token answer display. Write only approved turns to `./storage/cases/` (same as API per ISSUE-010).

### `src/advogado_de_bolso/config.py`
See `17-config-and-docs-modifications.md` for the env alias and wiring requirement.

### `.env.example`
See `17-config-and-docs-modifications.md` for the `CASES_PATH` entry.

### `README.md`
See `17-config-and-docs-modifications.md` for the dev/prod/single-worker notes.

### `tests/test_calculos.py`
Rewrite (see `15-backend-tests.md`).

### `tests/test_redigir.py`
Rewrite (see `15-backend-tests.md`).

### `tests/test_rag_tool.py`
Rewrite (see `15-backend-tests.md`).

### `tests/test_api.py`
Rewrite (see `15-backend-tests.md`).

### `tests/test_service.py`
Rewrite (see `15-backend-tests.md`).

### `tests/test_agent.py`
Extend (see `15-backend-tests.md`).

### `tests/test_config.py`
See `17-config-and-docs-modifications.md` for the env-override test.

### `base_frontend/package.json`
Full rewrite; see `10-frontend-build-and-config.md` for the complete script/dep spec.

### `base_frontend/vite.config.ts`
`server.proxy` addition; see `10-frontend-build-and-config.md` for the complete spec.

### `base_frontend/src/App.tsx`
Full handler rewrite; see `13-frontend-app.md` for the complete spec.

### `base_frontend/src/types.ts`
Add `is_demo?`; see `11-frontend-types-and-defaults.md`.

### `base_frontend/src/components/ChatInterface.tsx`
Rename `isLoading` to `isSendingMessage`; see `13-frontend-app.md`.

### `base_frontend/src/defaults.ts` (new, additional spec)
`initialPreferences` + `seedCases`; see `11-frontend-types-and-defaults.md`.

