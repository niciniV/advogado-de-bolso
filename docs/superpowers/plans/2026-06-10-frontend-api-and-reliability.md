# Frontend API and Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a tested FastAPI connection, responsive reference frontend, complete integration documentation, and audited backend reliability fixes.

**Architecture:** Keep the current agent and knowledge-index domain code, add an injectable chat-service and FastAPI transport boundary, and serve a dependency-free reference frontend from the same process. Make safety-sensitive behavior fail-closed and keep browser/API session data bounded and in memory.

**Tech Stack:** Python 3.11, FastAPI, Pydantic AI, pytest, Ruff, mypy, HTML, CSS, JavaScript

---

### Task 1: Make audited backend behavior safe and typed

**Files:**
- Modify: `src/advogado_de_bolso/config.py`
- Modify: `src/advogado_de_bolso/agent.py`
- Modify: `src/advogado_de_bolso/cli.py`
- Modify: `src/advogado_de_bolso/knowledge/index.py`
- Modify: `src/advogado_de_bolso/ingest.py`
- Modify: `src/advogado_de_bolso/tools/rag.py`
- Modify: `src/advogado_de_bolso/tools/revisor.py`
- Test: `tests/test_config.py`
- Test: `tests/test_agent.py`
- Test: `tests/test_knowledge_index.py`
- Test: `tests/test_rag_tool.py`
- Test: `tests/test_revisor.py`
- Test: `tests/test_revision_result.py`

- [ ] Write regression tests for revision contradictions, bounded retrieval,
  credential precedence, and full index replacement.
- [ ] Run the focused tests and confirm the new assertions fail for the expected
  missing behavior.
- [ ] Implement the minimal safety fixes and strict type annotations.
- [ ] Run focused tests, then `uv run pytest -q`, `uv run ruff check .`, and
  `uv run mypy src`.

### Task 2: Add the injectable chat service and HTTP API

**Files:**
- Create: `src/advogado_de_bolso/service.py`
- Create: `src/advogado_de_bolso/api.py`
- Create: `tests/test_service.py`
- Create: `tests/test_api.py`
- Modify: `src/advogado_de_bolso/config.py`
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] Write failing service tests for session creation, bounded history, reset,
  and serialized access.
- [ ] Write failing API tests for health, chat, validation, reset, and generic
  runtime errors using an injected fake service.
- [ ] Run focused tests and confirm failure because the new modules do not exist.
- [ ] Implement the chat service, runtime factory, routes, CORS, and `advogado-api`
  script.
- [ ] Run focused tests and all Python verification gates.

### Task 3: Add the responsive reference frontend and integration guide

**Files:**
- Create: `src/advogado_de_bolso/frontend/index.html`
- Create: `src/advogado_de_bolso/frontend/styles.css`
- Create: `src/advogado_de_bolso/frontend/app.js`
- Create: `README.md`
- Modify: `pyproject.toml`
- Test: `tests/test_api.py`

- [ ] Add failing API assertions that the root page and frontend assets are
  served with the expected content types.
- [ ] Run the focused API tests and confirm the frontend assertions fail.
- [ ] Implement the accessible mobile-first frontend and serve its assets.
- [ ] Document local setup, API contract, client examples, responsive behavior,
  privacy, CORS, production hardening, and verification.
- [ ] Run the complete verification suite and inspect the frontend in the
  in-app browser.

### Task 4: Independent review and publication

**Files:**
- Review: all changed files

- [ ] Dispatch independent subagents for specification compliance, code quality,
  API/security risks, and frontend usability.
- [ ] Fix all critical and important findings and rerun the relevant checks.
- [ ] Run fresh final tests, Ruff, mypy, and build verification.
- [ ] Inspect the final diff, stage intended files, commit, and push `main` to
  `origin`.
