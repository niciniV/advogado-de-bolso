# Frontend API and Reliability Design

## Goal

Expose Advogado de Bolso through a stable HTTP API and a responsive reference
frontend while fixing the reliability, privacy, and type-safety issues found in
the repository audit.

## Architecture

The existing agent, tools, and knowledge index remain the domain layer. A new
FastAPI application becomes the transport boundary and owns runtime startup,
request validation, CORS, session histories, and error mapping. The API uses an
injectable chat service so route tests do not initialize an embedding model or
call an external LLM.

The reference frontend is a dependency-free HTML/CSS/JavaScript application
served by FastAPI. It demonstrates the complete browser integration without
forcing downstream teams to adopt a frontend framework. Its API contract is
documented so React, Vue, mobile, and other clients can replace it directly.

## API Contract

- `GET /api/health` returns service readiness and never exposes credentials.
- `POST /api/chat` accepts `message` and an optional `session_id`, then returns
  the assistant response and stable session identifier.
- `DELETE /api/sessions/{session_id}` clears server-side conversation history.
- `GET /` serves the reference frontend.
- Invalid requests return FastAPI's structured `422` response.
- Runtime failures return a generic Portuguese `503` response and are logged
  server-side without exposing secrets.

Sessions are stored in memory only. They expire when the process restarts and
have bounded histories. Per-session locks prevent concurrent requests from
corrupting conversation ordering.

## Responsive Frontend

The reference frontend uses a mobile-first single-column chat layout that grows
into a centered desktop workspace. It includes clear empty, loading, success,
and error states; accessible labels and focus styles; disabled submit behavior
during a request; and a visible session reset control. The visual direction is
warm, editorial, and civic rather than a generic dashboard.

The browser stores only the opaque session identifier in `sessionStorage`.
Messages stay in the page DOM for the current tab and are not persisted to
local storage.

## Reliability and Safety Fixes

- Revision results become fail-closed and reject contradictory approval states.
- Retrieval size configuration is bounded and request-level `top_k` can only
  narrow the configured retriever result set.
- CLI prompt history becomes in-memory by default so sensitive legal questions
  are not silently persisted.
- The preferred configured Gemini key is applied deterministically.
- Full ingestion replaces the existing collection so deleted or changed source
  documents cannot leave stale legal material behind.
- Existing strict mypy failures are corrected and type checking becomes a
  documented verification gate.

## Testing

Tests cover the API contract with an injected fake chat service, session
creation/reset and history bounds, revision contradiction handling, retrieval
limits, credential precedence, and destructive full-ingestion replacement.
Existing tests remain unchanged unless the corrected behavior requires a new
expectation.

## Documentation

The root README explains installation, ingestion, CLI use, API startup,
environment variables, endpoints, browser integration, production deployment,
CORS, responsive frontend guidance, privacy, and the verification commands.
