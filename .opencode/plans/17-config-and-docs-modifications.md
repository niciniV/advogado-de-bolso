# 17-config-and-docs-modifications.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1011-1012 + 1174-1181 + 1201-1202)
**In this file:** "Files to Modify" — `config.py` (cases_path env alias + injection), `.env.example` (CASES_PATH), `README.md` (dev/prod/single-worker notes), `tests/test_config.py` (env override test).
**Related files:** [09-cli-config-deps.md](./09-cli-config-deps.md) (the `config.py` addition also spec'd in the Files to Create section), [04-storage.md](./04-storage.md) (the `cases_path` value is used by the storage layer), [06-service-class.md](./06-service-class.md) (the `cases_path` is injected into `ChatService`).

### `src/advogado_de_bolso/config.py`
Add `cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")` (ISSUE-M3-014). The env alias keeps `Settings` consistent with `DATA_PATH` / `CHROMA_PATH` / `HF_HOME` which all use `Field(..., alias=...)`. **Also ensure the value is wired into the service via `build_chat_service(settings, deps_factory)` → `ChatService(..., cases_path=settings.cases_path)`** (ISSUE-USR-007); without that injection the env var is dead.

### `.env.example`
Add `CASES_PATH=./storage/cases` next to `CHROMA_PATH`.

### `README.md`
Document `make dev`, `make frontend`, production startup with `uv run advogado-api`, the required single-worker deployment mode, the `<1000` case-file assumption, and unsupported concurrent API + CLI writes.

### `tests/test_config.py`
Add a test that `CASES_PATH` overrides the default and produces a `Path`.

