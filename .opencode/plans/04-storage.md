# 04-storage.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** `src/advogado_de_bolso/storage/cases.py` spec — `Case` model, `load`/`save`/`delete`/`list_all` signatures, path containment, atomic writes, lock retention; plus the empty `storage/__init__.py` package init.
**Related files:** [06-service-class.md](./06-service-class.md) (consumer of these storage functions via the `cases_path` injection), [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) (the `CASES_PATH` env alias is configured here), [15-backend-tests.md](./15-backend-tests.md) (`test_storage.py` pins the atomic-write and round-trip behavior).

### `src/advogado_de_bolso/storage/__init__.py`
Empty package init.

### `src/advogado_de_bolso/storage/cases.py`
Per-case JSON persistence. **No `_index.json`**: `list_all()` scans the directory directly.

- `Case` model: `id, title, created_at, updated_at, response_style, icon_name, is_demo, chat_history: list[ChatMessage], model_history: list[ModelMessage]`
  - `model_history` is the LLM-bound history (raw `ModelMessage` objects appended from `result.new_messages()` on each turn) and is **required** for multi-turn quality (ISSUE-M3-001 + ISSUE-USR-002). It preserves `ToolCallPart`/`ToolReturnPart` payloads across turns. The wire `chat_history` is for the UI; `model_history` is for the LLM. Critically, persistence uses `result.new_messages()` (current turn only) — not `result.all_messages()` — so prior turns' tool returns are not double-counted.
- Functions: `load(case_id, *, cases_path: Path)`, `save(case, *, cases_path: Path)`, `delete(case_id, *, cases_path: Path)`, `list_all(*, cases_path: Path) -> list[CaseSummary]`. **All four functions take a `cases_path: Path` keyword-only argument** (ISSUE-USR-007); the `ChatService` passes `self._cases_path` (which it received from `Settings.cases_path`) on every call. The functions MUST NOT hardcode `./storage/cases` — doing so would defeat the `CASES_PATH` env var.
- File layout: `./storage/cases/{case_id}.json` (configurable via `Settings.cases_path` with env alias `CASES_PATH` — see ISSUE-M3-014 + ISSUE-USR-007)
- **Path containment and UUID invariant** (ISSUE-USR-001): every storage function (`load`, `save`, `delete`) takes a canonical UUID string and constructs `cases_path / f"{case_id}.json"`. After construction, the resolved absolute path MUST satisfy `file_path.resolve().is_relative_to(cases_path.resolve())`; otherwise the function raises `ValueError`. `StructuredChatRequest.session_id` and every `/api/cases/{case_id}` path parameter are typed as `UUID`; service entry points accept `UUID` and convert once with `str(case_id)` before lock/storage access. The only non-client ID source is a freshly-generated `uuid.uuid4()`.
- **Directory creation**: `save()` calls `file_path.parent.mkdir(parents=True, exist_ok=True)` before writing. The `cases_path` is also created at `ChatService.__init__` time so the first save is a no-op directory-wise. See ISSUE-005.
- Atomic writes: write to a unique same-directory temp path such as `.{case_id}.{uuid4().hex}.tmp`, flush and close it, then call `os.replace(tmp, final)`. Clean up that specific temp path in `finally`. Unique temp names prevent concurrent writers from clobbering each other's temporary file.
- Atomic replacement prevents torn/partially-written JSON, but it does **not** prevent cross-process lost updates. Concurrent API + CLI read-modify-write operations on the same case are explicitly unsupported and use last-writer-wins semantics. Do not describe `os.replace()` as full cross-process write safety.
- Per-case `asyncio.Lock` retained for the service lifetime. The lock registry uses a single meta-lock to protect creation/lookups. Do **not** pop a lock on delete: a waiter may already hold a reference to the old lock, and creating a replacement lock would break serialization. The bounded `<1000`-case deployment assumption makes retaining at most one lightweight lock per observed UUID acceptable.
- `list_all()` reads each `{case_id}.json` and returns a `CaseSummary` for each. For <1000 cases this is fast enough; no index file is needed.
- **Scalability constraint** (ISSUE-DS-007): the `list_all()` docstring MUST document that this implementation is acceptable only for `<1000` case files. Each call performs one `json.loads` per file plus one `os.listdir`. Above 1000 cases, latency degrades linearly. A soft warning is logged at `INFO` level when the file count exceeds 500. See Out-of-Scope Notes for the upgrade path.

