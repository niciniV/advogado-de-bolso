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

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `adapter.py` | `extract_structured_response`, `_extract_questions`, `_extract_suggestive_text`, `_derive_quick_replies`, `_DEFAULT_QUICK_REPLIES`, `_DEADLINE_QUICK_REPLIES`, `_DOC_QUICK_REPLIES` | **NEW (batch 2).** Pure function that turns agent prose + `ToolReturnPart`s into a `StructuredChatResponse`. Three helpers above the main entrypoint handle question / suggestive-text / quick-reply extraction. |
| `agent.py` | `build_agent(settings)`, `SYSTEM_PROMPT` | Constructs Pydantic AI agent, registers all tools (still under the pre-batch-4 design; rewired in batch 4) |
| `api.py` | `create_app()`, `app`, `run()` | FastAPI app factory, `/api/chat`, `/api/health`, session endpoints (still under the pre-batch-4 design; rewired in batch 4) |
| `cli.py` | `app()` | Interactive REPL: `prompt_toolkit` input, `rich` markdown streaming, slash commands (`/sair`, `/limpar`, `/ajuda`, `/modelo`) (still under the pre-batch-4 design; rewired in batch 5) |
| `config.py` | `Settings`, `get_settings()` | Pydantic BaseSettings: LLM keys, model, embedding, paths, API host/port, CORS. Singleton via `@lru_cache` |
| `contracts.py` | `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk`, `TipoPrazo`, `Tom` | Typed tool return envelopes (Pydantic BaseModel). Successes return these; errors return plain `str`. `Tom` is defined canonically here and re-exported by `tools/redigir.py`. |
| `deps.py` | `Deps` | Dataclass injecting `settings` + `retriever` into agent tool calls |
| `schemas.py` | `StructuredChatRequest`, `StructuredChatResponse`, `CaseSummary`, `CaseResponse`, `ChatMessage`, `UpdateCaseRequest`, `CaseTitle`, `IconName`, `ResponseStyle` | **NEW (batch 2).** Wire types for the HTTP API. All fields snake_case; `StringConstraints` for `message`/`title`; `Literal` aliases for `icon_name`/`response_style`; `ConfigDict(extra="forbid")` + `model_validator` on `UpdateCaseRequest`; `StructuredChatResponse.updated_at` and `.chat_history` have assembly-safe defaults. |
| `service.py` | `ChatService`, `AgentChatBackend`, `build_chat_service()` | Session management (OrderedDict, lock, history truncation), review gate, backend adapter (still under the pre-batch-4 design; rewired in batch 4) |
| `storage/__init__.py` | - | **NEW (batch 3).** Empty package init for the storage subpackage. |
| `storage/cases.py` | `Case`, `load`, `save`, `delete`, `list_all` | **NEW (batch 3).** Per-case JSON persistence. One JSON file per case at `{cases_path}/{case_id}.json`. Atomic writes via `.{case_id}.{uuid4().hex}.tmp` + `os.replace`. Path containment via `is_relative_to`. Directory creation on `save`. `Case.model_history` round-trips as `ModelMessage` objects; `ToolReturnPart.content` becomes a `dict` (ISSUE-USR-016). |
| `__init__.py` | `__version__` | Package version `"0.1.0"` |
| `__main__.py` | - | Entry point: delegates to `cli.app()` |

## Work Guidance

- `build_agent()` in `agent.py` constructs the main agent with 3 tools: `search_knowledge_base`, `calcular_prazo_consumidor`, `redigir_documento`
- `ChatService` owns in-memory session state with bounded history (`max_history_messages=40`, `max_sessions=500`)
- `AgentChatBackend.run()` calls agent then runs `review_response()` - blocks delivery if not approved
- `build_chat_service()` wires everything: KnowledgeIndex -> Deps -> Agent -> Backend -> Service
- CLI uses `prompt_toolkit` + `rich` for interactive chat with live streaming
- API uses FastAPI with CORS, lazy lifespan (builds service on first request), health check

## Verification

- `ruff check src/` for linting
- `mypy src/` for type checking
- `pytest tests/` for unit tests

## Child DOX Index

- `knowledge/` - Vector index, document loaders, ChromaDB integration
- `storage/` - Per-case JSON persistence (batch 3); see `storage/AGENTS.md`
- `tools/` - Agent tools: RAG search, deadline calculations, document drafting, response review
