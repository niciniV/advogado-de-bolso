# 20-implementation-order.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1293-1305)
**In this file:** The 9-step gated implementation order with per-step pytest/ruff/mypy gates (ISSUE-M3-018).
**Related files:** [21-functional-checks.md](./21-functional-checks.md) (the 21 functional verification scenarios run after the implementation completes), [15-backend-tests.md](./15-backend-tests.md) (the test files each batch gates against), [14-frontend-tests.md](./14-frontend-tests.md) (the frontend test files the Frontend integration batch gates against).

## Verification

### Implementation order (ISSUE-M3-018)
The implementation uses gated batches. Tests may intentionally fail inside a batch while its production code and tests are being changed together. Do not start the next batch until the current batch's stated gate is green.

1. **Typed tool contracts batch:** add `contracts.py`; update `tests/test_calculos.py`, `tests/test_redigir.py`, and `tests/test_rag_tool.py` to express the new contract and verify they fail for the expected old-string behavior; refactor the three tools; run `uv run pytest tests/test_calculos.py tests/test_redigir.py tests/test_rag_tool.py` and then `uv run pytest`. Both must pass.
2. **Storage batch:** add `storage/__init__.py`, `storage/cases.py`, and `tests/test_storage.py`; run `uv run pytest tests/test_storage.py` and then `uv run pytest`.
3. **Schema/adapter batch:** add `schemas.py`, `adapter.py`, and `tests/test_adapter.py`; run `uv run pytest tests/test_adapter.py` and then `uv run pytest`.
4. **Service/API batch:** add `Settings.cases_path`, update `.env.example`, rewrite `agent.py`, `service.py`, and `api.py`, then rewrite/extend `tests/test_config.py`, `tests/test_agent.py`, `tests/test_service.py`, and `tests/test_api.py`; run those four test files, `uv run pytest`, `uv run ruff check src/ tests/`, and `uv run mypy src/`.
5. **CLI batch:** rewrite `cli.py` and add `tests/test_cli.py`; run `uv run pytest tests/test_cli.py` and then `uv run pytest`.
6. **Frontend dependency batch:** rewrite `base_frontend/package.json`, add the Vitest dependencies/scripts, run `npm install` in `base_frontend` to generate `base_frontend/package-lock.json`, and add the Vite proxy/test configuration. Do not use `npm ci` until the lockfile exists.
7. **Frontend integration batch:** add `src/api.ts`, `src/defaults.ts`, `src/api.test.ts`, and `src/App.test.tsx`; refactor `App.tsx`, `ChatInterface.tsx`, and any affected components/types; delete `server.ts`; run `npm run test`, `npm run lint`, and `npm run build`.
8. **Operations/docs batch:** add the `Makefile`; update `README.md` with production/dev commands, single-worker requirement, `<1000` case constraint, and API/CLI concurrent-write limitation; run every command in Functional Checks that does not require live model credentials.
9. **Final gate:** run `uv run pytest`, `uv run ruff check src/ tests/`, `uv run mypy src/`, `cd base_frontend && npm ci`, `npm run test`, `npm run lint`, and `npm run build`.

