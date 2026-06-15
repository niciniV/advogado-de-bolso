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
- **Tool return shapes are typed envelopes** (`contracts.py`): `calcular_prazo_consumidor` returns `DeadlineResult` (success) or `str` (error path: missing `tipo_item`, invalid date, invalid `tipo_prazo`); `redigir_documento` returns `DraftedDocument`; `search_knowledge_base` returns `list[KnowledgeChunk]`. The adapter (added in a later batch) dispatches on `isinstance(part.content, X)` and ignores `str` returns.
- The `Tom` alias for `redigir_documento` is the canonical `contracts.Tom`; do not redeclare it locally in `tools/redigir.py`.

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `agent.py` | `build_agent(settings)`, `SYSTEM_PROMPT` | Constructs Pydantic AI agent, registers all tools |
| `api.py` | `create_app()`, `app`, `run()` | FastAPI app factory, `/api/chat` POST, `/api/health` GET, `/api/sessions/{id}` DELETE, static frontend mount |
| `cli.py` | `app()` | Interactive REPL: `prompt_toolkit` input, `rich` markdown streaming, slash commands (`/sair`, `/limpar`, `/ajuda`, `/modelo`) |
| `config.py` | `Settings`, `get_settings()` | Pydantic BaseSettings: LLM keys, model, embedding, paths, API host/port, CORS. Singleton via `@lru_cache` |
| `contracts.py` | `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk`, `TipoPrazo`, `Tom` | Typed tool return envelopes (Pydantic BaseModel). Successes return these; errors return plain `str`. `Tom` is defined canonically here and re-exported by `tools/redigir.py`. |
| `deps.py` | `Deps` | Dataclass injecting `settings` + `retriever` into agent tool calls |
| `service.py` | `ChatService`, `AgentChatBackend`, `build_chat_service()` | Session management (OrderedDict, lock, history truncation), review gate, backend adapter |
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
- `tools/` - Agent tools: RAG search, deadline calculations, document drafting, response review
