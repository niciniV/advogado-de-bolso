# 08-api.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** `src/advogado_de_bolso/api.py` spec — endpoint list, UUID-typed path parameters, CORS, static serving / explicit SPA fallback, blocked-envelope 422 contract, 503 error handler.
**Related files:** [02-schemas.md](./02-schemas.md) (request/response wire types the endpoints consume/produce), [06-service-class.md](./06-service-class.md) (the `ChatService` that the API delegates to), [10-frontend-build-and-config.md](./10-frontend-build-and-config.md) (`vite.config.ts` proxy and `Makefile` frontend build target that pair with this API).

### `src/advogado_de_bolso/api.py`
Major rewrite. Drop `/api/chat` and `/api/sessions`. Add the new case endpoints. Use **explicit SPA fallback** (not `StaticFiles(html=True)`). Return `422` for blocked responses.

**Endpoints:**
- `POST /api/chat/structured` (body: `StructuredChatRequest`) → full `StructuredChatResponse` on both success (200) and reviewer block (422). The blocked envelope includes `session_id`, unchanged persisted `chat_history`, `blocked=true`, and `blocked_message`; it never includes rejected prose/tool-derived structured data.
- `GET /api/cases` → `list[CaseSummary]`
- `GET /api/cases/{case_id}` with `case_id: UUID` → `CaseResponse` (added per ISSUE-USR-005 — required by tests and the frontend `handleSelectCase` flow, which was previously undocumented in the endpoint list). Delegates to `ChatService.get_case(case_id)`.
- `PATCH /api/cases/{case_id}` with `case_id: UUID` (body: `UpdateCaseRequest`) → `CaseResponse`. Delegates to `ChatService.update_case_meta` (ISSUE-M3-008 + ISSUE-USR-005) so per-field validation lives in the service. The body uses `UpdateCaseRequest { title?, icon_name?, response_style? }`, not the old `RenameCaseRequest { title }`. **This endpoint also serves the rename flow** (ISSUE-IND-002): the frontend's `apiClient.renameCase(caseId, newTitle)` is a thin client-side wrapper that calls `apiClient.updateCaseMeta(caseId, { title: newTitle })`, which issues a PATCH with `{ title }` to this same endpoint. There is no dedicated `rename_case` method on `ChatService`; the PATCH endpoint is the single metadata-update surface.
  - Call `payload.model_dump(exclude_unset=True)` when forwarding fields. Convert `KeyError` from a missing case to HTTP 404 and `ValueError` from service validation to HTTP 422; do not let either become the generic 503 handler.
- `DELETE /api/cases/{case_id}` with `case_id: UUID` → 204
- `GET /api/cases/{case_id}/history` with `case_id: UUID` → `list[ChatMessage]`
- Every case path parameter is UUID-typed in the FastAPI function signature. Malformed IDs return FastAPI/Pydantic `422` before service or storage access.
- `GET /api/health` (kept)

**Dropped endpoints:** `POST /api/chat`, `DELETE /api/sessions/{session_id}`, `POST /api/cases` (per Open Issue #5 = A), `PUT /api/cases/{case_id}` (per Open Issue #14 = A).

**CORS:** `allow_methods = ["GET", "POST", "PATCH", "DELETE"]` (no PUT — removed). The current `api.py:92` has `allow_methods=["GET", "POST", "DELETE"]` and is missing `"PATCH"` (ISSUE-DS-004). Add it.

**Static serving:**
```python
# `api.py` lives at `<project_root>/src/advogado_de_bolso/api.py`, so:
#   .parent              → .../advogado_de_bolso/
#   .parent.parent       → .../src/
#   .parent.parent.parent → <project_root>          ← three parents
#   .parent.parent.parent.parent → one level ABOVE the project root (WRONG)
REACT_DIST = Path(__file__).parent.parent.parent / "base_frontend" / "dist"
```

```python
# Asset mount first (specific path)
if REACT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=REACT_DIST / "assets"), name="react-assets")

# SPA fallback: explicit, excludes /api and /assets. Use exact
# first-segment matching (ISSUE-009) so `/apiary` is NOT treated as
# `/api/...` and `/assetsManager` is NOT treated as `/assets/...`.
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    first_segment = full_path.split("/", 1)[0] if full_path else ""
    if first_segment in {"api", "assets"}:
        raise HTTPException(404, "Not Found")
    index = REACT_DIST / "index.html"
    if not index.exists():
        raise HTTPException(500, "Frontend bundle not built. Run `make frontend`.")
    return FileResponse(index)
```

This prevents the `StaticFiles(html=True)`-style behavior where `/api/chatt` (typo) returns 200 + `index.html` and the frontend breaks parsing JSON.

**Block envelope:** The `422` response body is `StructuredChatResponse` with `blocked=True`:
```python
# ISSUE-USR-008: `model_dump()` returns Python `date` objects from
# `DeadlineResult.data_inicio` / `data_limite`. Starlette's `JSONResponse`
# uses stdlib `json.dumps`, which raises `TypeError: Object of type date
# is not JSON serializable`. Use `model_dump(mode="json")` to coerce
# dates (and any other non-JSON-native types) to ISO-8601 strings.
# Alternatively, wrap the content with `jsonable_encoder` from
# `fastapi.encoders` — both are correct; `mode="json"` is preferred
# because it stays inside the Pydantic model layer.
if result.response.blocked:
    return JSONResponse(
        status_code=422,
        content=result.response.model_dump(mode="json"),
    )
return result.response
```

The API layer wraps `chat_structured` calls in a `try/except` and converts unhandled backend / save exceptions to `503 Service Unavailable` (ISSUE-M3-015). The frontend MUST parse the body on `!response.ok` to surface `blocked_message` to the user (ISSUE-DS-002).

