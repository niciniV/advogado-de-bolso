# advogado_de_bolso - Main Package

## Purpose

Core application package for the "Advogado de Bolso" chatbot - an agentic assistant for Brazilian consumer rights (CDC/Lei 8.078/90).

## Ownership

- Main agent definition and tool registration
- Application service layer (session management, chat backend)
- Configuration and dependency injection
- CLI and HTTP API transports

## Local Contracts

- All user-facing text MUST be in Brazilian Portuguese
- Never fabricate legal articles, process numbers, or dates
- Always recommend professional legal counsel for complex cases
- Agent responses must be reviewed before delivery (revisor tool)
- All settings loaded from environment variables via pydantic-settings
- **Tool return shapes are typed envelopes** (`contracts.py`): `calcular_prazo_consumidor` returns `DeadlineResult` (success) or `str` (error path: missing `tipo_item`, invalid date, invalid `tipo_prazo`); `redigir_documento` returns `DraftedDocument`; `search_knowledge_base` returns `list[KnowledgeChunk]`. The adapter (`adapter.py`) dispatches on `isinstance(part.content, X)` keyed by `part.tool_name` and gracefully ignores `str` returns and unknown tool names.
- The `Tom` alias for `redigir_documento` is the canonical `contracts.Tom`; do not redeclare it locally in `tools/redigir.py`.
- **Wire types** (`schemas.py`): all fields are snake_case and validated at the API boundary so a malformed request returns 422 BEFORE the service runs (ISSUE-REVIEW-007). `StructuredChatRequest` / `Response`, `CaseSummary` / `CaseResponse`, `ChatMessage`, and `UpdateCaseRequest` are the public HTTP types; `StructuredChatResponse.updated_at` and `.chat_history` have assembly-safe defaults (ISSUE-USR-015) so the adapter can construct the response before the service appends the current turn. `UpdateCaseRequest` has `model_config = ConfigDict(extra="forbid")` and a `model_validator` that rejects empty bodies (USR-005 / M3-008).
- **Adapter dispatch contract** (`adapter.py`): `extract_structured_response(prose, tool_returns, *, blocked=False, blocked_message=None) -> StructuredChatResponse` is a pure function. Dispatch is by `tool_name` (string) and uses `isinstance(content, X)` to identify typed envelopes — this works in-memory because Pydantic AI stores the raw Python object on `ToolReturnPart.content` (per `BaseToolReturnPart.content: ToolReturnContent` in pydantic-ai>=1.106). Unknown tool names log a WARNING and are silently ignored (ISSUE-DS-006). The JSON round-trip degrades `content` to a `dict`; the typed-identity guarantee holds only in-memory. The adapter also extracts `questions` (regex over prose, 5-item cap, dedup), `suggestive_text` (last non-empty line, 200-char cap), and `quick_replies` (contextual: deadline / doc / default chip sets).
- **Case persistence on disk** (`storage/cases.py`): one JSON file per case at `{cases_path}/{case_id}.json`. Disk is the source of truth. **No** `_index.json`: `list_all()` scans the directory directly. All four functions (`load` / `save` / `delete` / `list_all`) take `cases_path: Path` as a keyword-only argument so the service layer can inject `Settings.cases_path` (ISSUE-USR-007); they MUST NOT hardcode `./storage/cases`. Path containment is enforced in every entrypoint via `file_path.resolve().is_relative_to(cases_path.resolve())` (ISSUE-USR-001); a `case_id` like `../../etc/passwd` raises `ValueError`. `save()` creates the parent directory if missing (ISSUE-005) and writes atomically via a unique same-directory temp path `.{case_id}.{uuid4().hex}.tmp` + `os.replace`; concurrent API + CLI read-modify-write on the same case are explicitly last-writer-wins (the atomic replacement prevents torn JSON but not cross-process lost updates). The `Case` model includes `model_history: list[ModelMessage]` for the LLM-bound history (raw `ModelMessage` objects with `ToolCallPart`/`ToolReturnPart` payloads); after a JSON round-trip the `ModelMessage` structure is preserved via the Pydantic `kind` discriminator, but `ToolReturnPart.content` degrades to a `dict` (ISSUE-USR-016). `list_all()` is documented as acceptable for `<1000` case files and logs an INFO warning at `>500` (ISSUE-DS-007).
- **Service layer is disk-persistent** (`service.py`, batch 4): `ChatService` no longer keeps in-memory sessions. Each `chat_structured` call acquires a per-case `asyncio.Lock` (registry is retained for the service lifetime, even after `delete_case`, to prevent the old-lock/new-lock race per ISSUE-M3-006), loads or creates the in-memory `Case`, runs the agent, runs the reviewer (exactly once per turn), then either persists the approved turn (appends to `chat_history` and `model_history`) or returns a blocked envelope (no save, returns the persisted `chat_history` snapshot). Blocked first messages do NOT create a case file (ISSUE-USR-004).
- **Response style propagation** (batch 4): the agent's `@agent.instructions` callback reads the `_current_style` ContextVar. `ChatService.chat_structured` sets it for the duration of the request and resets it in a `finally` (ISSUE-DS-008). The fallback chain is: request `response_style` > persisted `case.response_style` > `"detalhado"`. `deps.py` does NOT carry `response_style`; sub-agents do not read the ContextVar.
- **API blocked envelope** (batch 4): when the reviewer blocks, `POST /api/chat/structured` returns HTTP 422 with the full `StructuredChatResponse` body (`blocked=true`, `blocked_message`, unchanged persisted `chat_history`). The body is serialized via `model_dump(mode="json")` so `DeadlineResult.date` fields become ISO-8601 strings (ISSUE-USR-008). The API catches unhandled backend/save exceptions and returns 503 (ISSUE-M3-015).

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `adapter.py` | `extract_structured_response`, `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`, `_DEFAULT_QUICK_REPLIES`, `_DEADLINE_QUICK_REPLIES`, `_DOC_QUICK_REPLIES` | **NEW (batch 2).** Pure function that turns agent prose + `ToolReturnPart`s into a `StructuredChatResponse`. Three helpers above the main entrypoint handle question / suggestive-text / quick-reply extraction. |
| `agent.py` | `build_agent(settings)`, `SYSTEM_PROMPT`, `STYLE_PROMPTS`, `_current_style` (ContextVar) | **REWRITTEN (batch 4).** Constructs the Pydantic AI agent with the full merged `SYSTEM_PROMPT` (describing the new tool return shapes) plus a per-request style prompt injected via `@agent.instructions` reading from the `_current_style` ContextVar. Registers `search_knowledge_base`, `calcular_prazo_consumidor` (`tool_plain`), `redigir_documento`. |
| `api.py` | `create_app()`, `app`, `run()` | **REWRITTEN (batch 4).** FastAPI app factory. Endpoints: `POST /api/chat/structured` (200 success / 422 blocked), `GET /api/cases`, `GET /api/cases/{case_id}` (UUID, 200/404/422), `PATCH /api/cases/{case_id}` (UUID, `UpdateCaseRequest` body), `DELETE /api/cases/{case_id}` (UUID, 204/404), `GET /api/cases/{case_id}/history` (UUID, 200/404/422), `GET /api/health`. CORS `allow_methods=["GET", "POST", "PATCH", "DELETE"]`. Explicit SPA fallback (not `StaticFiles(html=True)`) excludes `/api` and `/assets` via first-segment match. `_to_case_response` hides `model_history` from the wire. |
| `cli.py` | `app()` | Interactive REPL: `prompt_toolkit` input, `rich` markdown streaming, slash commands (`/sair`, `/limpar`, `/ajuda`, `/modelo`) (still under the pre-batch-4 design; rewired in batch 5) |
| `config.py` | `Settings`, `get_settings()` | Pydantic BaseSettings: LLM keys, model, embedding, paths, API host/port, CORS. **NEW (batch 4):** `cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")` (ISSUE-M3-014). Singleton via `@lru_cache` |
| `contracts.py` | `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk`, `TipoPrazo`, `Tom` | Typed tool return envelopes (Pydantic BaseModel). Successes return these; errors return plain `str`. `Tom` is defined canonically here and re-exported by `tools/redigir.py`. |
| `deps.py` | `Deps` | Dataclass injecting `settings` + `retriever` into agent tool calls. **No changes in batch 4** — `response_style` is propagated via the `_current_style` ContextVar, not via `Deps`. |
| `schemas.py` | `StructuredChatRequest`, `StructuredChatResponse`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest`, `CaseTitle`, `IconName`, `ResponseStyle` | **NEW (batch 2).** Wire types for the HTTP API. All fields snake_case; `StringConstraints` for `message`/`title`; `Literal` aliases for `icon_name`/`response_style`; `ConfigDict(extra="forbid")` + `model_validator` on `UpdateCaseRequest`; `StructuredChatResponse.updated_at` and `.chat_history` have assembly-safe defaults. |
| `service.py` | `ChatService`, `AgentChatBackend`, `ChatResult`, `ChatBackend`, `ReviewerLike`, `REVIEW_BLOCKED_MESSAGE`, `build_chat_service()`, `_collect_tool_returns`, `_truncate_history_to_turns`, `_now`, `_now_ms` | **REWRITTEN (batch 4).** Disk-persistent `ChatService` with per-case `asyncio.Lock` registry retained for service lifetime. `chat_structured` (the new primary method) loads or creates the case, sets the `_current_style` ContextVar, runs the agent, runs the reviewer exactly once, then either persists (approved) or returns a blocked envelope (no save). `AgentChatBackend` does NOT run the reviewer. `ChatResult` is the renamed-from-`ChatReply` wrapper. `_truncate_history_to_turns` groups messages at user-prompt boundaries so tool call/return pairs stay paired. |
| `storage/__init__.py` | - | **NEW (batch 3).** Empty package init for the storage subpackage. |
| `storage/cases.py` | `Case`, `load`, `save`, `delete`, `list_all` | **NEW (batch 3).** Per-case JSON persistence. One JSON file per case at `{cases_path}/{case_id}.json`. Atomic writes via `.{case_id}.{uuid4().hex}.tmp` + `os.replace`. Path containment via `is_relative_to`. Directory creation on `save`. `Case.model_history` round-trips as `ModelMessage` objects; `ToolReturnPart.content` becomes a `dict` (ISSUE-USR-016). |
| `__init__.py` | `__version__` | Package version `"0.1.0"` |
| `__main__.py` | - | Entry point: delegates to `cli.app()` |

## Work Guidance

- `build_agent()` in `agent.py` constructs the main agent with 3 tools: `search_knowledge_base`, `calcular_prazo_consumidor`, `redigir_documento` — and the new `@agent.instructions` callback that returns the matching `STYLE_PROMPTS` entry for the request's `_current_style` ContextVar.
- `ChatService.chat_structured(message, session_id, *, response_style, title, icon_name) -> ChatResult` is the new primary method. The reviewer is called by the service exactly once per turn; the backend does NOT run the reviewer. The LLM-bound history is capped to the last N TURNS (default 20) via `_truncate_history_to_turns` so tool call/return pairs stay paired.
- `ChatService.update_case_meta(case_id, **fields)` validates and applies partial metadata updates (`title`, `icon_name`, `response_style`). The per-case lock is acquired to serialize with concurrent `chat_structured` and `delete_case` (ISSUE-USR-013).
- The per-case `asyncio.Lock` registry in `_case_locks` is retained for the service lifetime — do NOT pop on delete (ISSUE-M3-006).
- Disk is the source of truth. `chat_structured` either persists the approved turn to `{cases_path}/{case_id}.json` or returns a blocked envelope (no save). Blocked first messages do NOT create a case file (ISSUE-USR-004).
- `AgentChatBackend.run()` calls the agent and returns `(prose, new_messages)` where `new_messages` is `result.new_messages()` (current turn only — never `all_messages()` per ISSUE-USR-002).
- `build_chat_service(settings, deps_factory=None)` wires `KnowledgeIndex` → `Deps` → `AgentChatBackend(agent, deps_factory)` → `review_response` wrapper → `ChatService(cases_path=settings.cases_path)`. The `cases_path` is injected from `Settings.cases_path` so the `CASES_PATH` env var actually controls persistence (ISSUE-USR-007).
- CLI uses `prompt_toolkit` + `rich` for interactive chat with live streaming (still under the pre-batch-4 design; batch 5).
- API uses FastAPI with CORS, lazy lifespan (builds service on first request), health check. The `POST /api/chat/structured` endpoint catches unhandled exceptions and returns 503 (ISSUE-M3-015).

## Verification

- `ruff check src/` for linting
- `mypy src/` for type checking
- `pytest tests/` for unit tests

## Child DOX Index

- `knowledge/` - Vector index, document loaders, ChromaDB integration
- `storage/` - Per-case JSON persistence (batch 3); see `storage/AGENTS.md`
- `tools/` - Agent tools: RAG search, deadline calculations, document drafting, response review
