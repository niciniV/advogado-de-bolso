# storage - Per-case JSON Persistence (batch 3)

## Purpose

Owns the on-disk case file format and the four functions that read, write,
delete, and list cases. Disk is the source of truth; there is no `_index.json`.

## Ownership

- `Case` Pydantic model
- `load`, `save`, `delete`, `list_all` storage functions
- Path containment invariant and atomic-write pattern
- `list_all()` summary derivation (`last_message`, `tag_text`)

## Local Contracts

- **Layout**: one JSON file per case at `{cases_path}/{case_id}.json`. There
  is no `_index.json` — `list_all()` scans the directory directly.
- **`cases_path: Path` is a keyword-only argument** for all four functions
  (ISSUE-USR-007). The service layer passes `self._cases_path` (which it
  received from `Settings.cases_path`) on every call. The functions MUST
  NOT hardcode `./storage/cases` — doing so would defeat the `CASES_PATH`
  env var (configured in batch 4).
- **Path containment** (ISSUE-USR-001): every entrypoint constructs
  `cases_path / f"{case_id}.json"` and raises `ValueError` if the resolved
  path is not `is_relative_to(cases_path.resolve())`. The API layer
  validates that `case_id` is a canonical UUID string before it reaches
  the storage layer; this is a defense-in-depth check.
- **Directory creation** (ISSUE-005): `save()` calls
  `file_path.parent.mkdir(parents=True, exist_ok=True)` before writing.
  The `cases_path` is also created at `ChatService.__init__` time (batch 4)
  so the first save is a no-op directory-wise.
- **Atomic writes**: `save()` writes to a unique same-directory temp path
  `.{case_id}.{uuid4().hex}.tmp`, flushes, then calls `os.replace()` to
  swap it onto the final path. The unique temp name prevents two
  concurrent writers of the same case from clobbering each other's
  temporary file. The temp file is cleaned up in `finally` so a failed
  write does not leak `.tmp` files.
- **Atomic replacement prevents torn/partially-written JSON**, but it does
  NOT prevent cross-process lost updates. Concurrent API + CLI
  read-modify-write on the same case are explicitly unsupported and use
  last-writer-wins semantics.
- **`Case.id` is a canonical UUID string**. The storage functions do not
  validate UUID format; that's the service/API layer's job. The wire type
  `CaseSummary.id` is `UUID`; `list_all()` converts with `UUID(case.id)`.
- **Scalability** (ISSUE-DS-007): `list_all()` is acceptable for `<1000`
  case files (each call performs one `json.loads` per file plus one
  `os.listdir`). A soft INFO log warning is emitted when the file count
  exceeds 500. See `.opencode/plans/24-out-of-scope.md` for the upgrade
  path (an `_index.json` or a SQLite-backed store).

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `__init__.py` | - | Empty package init. |
| `cases.py` | `Case`, `load`, `save`, `delete`, `list_all` | All four functions take `cases_path: Path` keyword-only. `Case` is the persisted record (Pydantic BaseModel). `list_all` returns `CaseSummary` per JSON file. |

## Work Guidance

- `Case.model_history: list[ModelMessage]` carries the LLM-bound history
  (raw `ModelMessage` objects with `ToolCallPart`/`ToolReturnPart`
  payloads). The wire `chat_history` is for the UI; `model_history` is
  for the LLM. After a JSON round-trip, the `ModelMessage` structure
  is preserved via the Pydantic `kind` discriminator, but
  `ToolReturnPart.content` becomes a `dict` (ISSUE-USR-016) — this is
  expected and pinned by `tests/test_storage.py::TestCaseModel`.
- `list_all()` `last_message` derivation: prefer `step_content` (structured
  analysis) over `text` (raw agent output) on the last assistant message.
  Truncate to 80 chars with no ellipsis.
- `list_all()` `tag_text` derivation: deadline > template_letter > None
  (precedence fixed; the rightmost assistant message wins).
- `delete()` returns `True` if the file was removed, `False` if it did
  not exist. It does NOT raise on missing files — the service layer
  treats "not found" as a no-op.
- `load()` returns `None` for a missing file (soft "not found") rather
  than raising, so the service layer can treat missing files as "start
  a new case" without try/except.

## Verification

- `pytest tests/test_storage.py -v` — storage layer tests (29 cases).
- `ruff check src/advogado_de_bolso/storage/` — lint.
- `mypy src/advogado_de_bolso/storage/` — type check.

## Related Files

- `src/advogado_de_bolso/schemas.py` — `ChatMessage` (wire type used in
  `Case.chat_history`) and `CaseSummary` (returned by `list_all`).
- `src/advogado_de_bolso/config.py` — `Settings.cases_path` is wired in
  batch 4; the storage layer accepts it as a parameter rather than
  reading from settings.
- `src/advogado_de_bolso/service.py` — `ChatService` will inject
  `self._cases_path` on every call (batch 4).
- `tests/test_storage.py` — golden tests for the storage layer.
- `.opencode/plans/04-storage.md` — full storage spec.
- `.opencode/plans/15-backend-tests.md` — storage test spec.
