# 00-overview-and-architecture.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** Top-level title, "Replaces" note, and the 10-bullet Architecture Summary describing the FastAPI + Vite + Pydantic AI + tool-envelope design.
**Related files:** [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) (operationalizes the system-prompt design), [06-service-class.md](./06-service-class.md) (implements the case-persistence model described here), [08-api.md](./08-api.md) (implements the dev/prod + SPA fallback model), [19-files-to-delete.md](./19-files-to-delete.md) (the `server.ts` deletion noted in the Architecture Summary).

# Integration Plan (Revised v2): base_frontend React UI → Python FastAPI Backend

> **Replaces** `.opencode/plans/revised-integration-plan.md` — incorporates all consensus fixes from the 3-reviewer loop.

---

## Architecture Summary

- **Single FastAPI server** on port 8000 serves the API and (in prod) the React build.
- **Dev**: Vite standalone on port 5173 with `server.proxy` forwarding `/api/*` → FastAPI.
- **Prod**: `base_frontend/dist/` served via an explicit SPA fallback route (NOT `StaticFiles(html=True)`) on FastAPI. `/api/*` routes take precedence.
- **Adapter pipeline**: Tools return typed Pydantic `BaseModel` envelopes for success, plain strings for error paths. The adapter reads `ToolReturnPart.content` directly. Pydantic AI stores the raw Python return on `BaseToolReturnPart.content` (typed as `ToolReturnContent`, an alias union in Pydantic AI 1.106+; the `Any` top-level permits typed objects). The `tool_plain` round-trip is NOT guaranteed to preserve raw objects through every model provider (e.g., Google Gemini may stringify) — the implementer MUST add a contract test in `tests/test_adapter.py` that exercises the real Pydantic AI `tool_plain` execution path and asserts the resulting `ToolReturnPart.content` is a `DeadlineResult`. See ISSUE-006. Dispatch is by `tool_name` (not by type-tries), because `tool_kind` is `None` for user-defined tools (per the `ToolPartKind | None = None` annotation on `BaseToolReturnPart.tool_kind`).
- **Case persistence**: One JSON file per case at `./storage/cases/{case_id}.json`. Disk is the source of truth. `case_id == session_id == one UUID`. No `_index.json` — `list_all()` scans the directory directly (acceptable for <1000 cases). Per-case `asyncio.Lock` instances are retained for the lifetime of the single-process service; they are **not** removed on delete because replacing a lock while waiters still hold the old instance can permit concurrent writes. API path parameters and request session IDs are UUID-typed before they reach the service/storage layer.
- **`response_style` injection**: Pydantic AI's `@agent.instructions` decorator registers a callback that reads from a `ContextVar` set per `chat_structured` call. The agent is built **once** at startup; no per-request rebuild. `Deps` stays clean (no `response_style` field).
- **Error envelope**: Reviewer-blocked responses return HTTP `422 Unprocessable Entity` with the full `StructuredChatResponse` envelope. It includes `session_id`, the unchanged persisted `chat_history`, `blocked: true`, and `blocked_message`; structured fields derived from rejected prose/tool output are empty. The frontend handles it via the existing `!response.ok` branch and retains `session_id` for a retry.
- **Auto-create UX**: First chat message with `session_id: null` creates a case server-side. The frontend sends `title` and `icon_name` derived from the first user message in the request body. `handleSaveCaseFromChat` becomes a metadata update (`PATCH /api/cases/{case_id}` with `UpdateCaseRequest { title?, icon_name?, response_style? }`) that refreshes title/icon (ISSUE-USR-005).
- **Demo cases**: Three seed cases ship in `defaults.ts` marked `is_demo: true`. Demo IDs are intentionally non-UUID frontend-only IDs. Selecting, renaming, or deleting a demo is handled locally and MUST NOT call UUID-typed API routes. The frontend renders demos with a "DEMO" badge and clears them when the first real case is created.
- **CLI**: Stays on `agent.run_stream` + writes case files via the storage layer directly. Does not go through `ChatService`, but MUST run `review_response()` before displaying or persisting the generated answer. The spinner/live status is preserved while generation and review run; token-by-token answer display is intentionally removed because showing tokens before review would violate the mandatory review gate.
- **No Express, no Gemini direct calls.** `server.ts` deleted.

