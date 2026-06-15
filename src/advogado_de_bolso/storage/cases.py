"""Per-case JSON persistence (batch 3).

One JSON file per case at `{cases_path}/{case_id}.json`. Disk is the source
of truth; there is no `_index.json`. `list_all()` scans the directory and
returns a `CaseSummary` per JSON file.

All four functions take `cases_path: Path` as a keyword-only argument so the
service layer can inject `Settings.cases_path` (ISSUE-USR-007). The functions
do NOT hardcode `./storage/cases`; doing so would defeat the `CASES_PATH`
env var (configured in batch 4).

Path containment
---------------
Every entrypoint constructs `cases_path / f"{case_id}.json"` and raises
`ValueError` if the resolved path escapes `cases_path` (ISSUE-USR-001).
This is a defense-in-depth check; the API layer validates that `case_id`
is a canonical UUID string before it reaches the storage layer.

Atomic writes
-------------
Writes go to a unique same-directory temp path (`.{case_id}.{uuid4().hex}.tmp`),
are flushed, then `os.replace()`'d to the final path. The unique temp name
prevents two concurrent writers of the same case from clobbering each other's
temporary file. The temp path is cleaned up in `finally` so a failed write
does not leak `.tmp` files.

This atomic replacement prevents torn/partially-written JSON, but does NOT
prevent cross-process lost updates. Concurrent API + CLI read-modify-write
on the same case are explicitly unsupported (last-writer-wins).

Scalability
-----------
`list_all()` performs one `json.loads` per file plus one `os.listdir`.
For <1000 case files this is fast enough; a soft INFO log warning is emitted
when the file count exceeds 500 (ISSUE-DS-007). See
`.opencode/plans/24-out-of-scope.md` for the upgrade path (an `_index.json`
or a SQLite-backed store).

References
----------
- `.opencode/plans/04-storage.md` — storage spec.
- `.opencode/plans/15-backend-tests.md` — test spec.
- `schemas.py` — `ChatMessage` (wire type) and `CaseSummary`.
- `pydantic_ai.messages.ModelMessage` — LLM-bound history.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import UTC, datetime  # noqa: F401  (type-only: annotations)
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

from advogado_de_bolso.schemas import CaseSummary, ChatMessage, IconName, ResponseStyle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scalability thresholds (ISSUE-DS-007)
# ---------------------------------------------------------------------------

_LIST_ALL_INFO_THRESHOLD: Final[int] = 500
_LIST_ALL_DOC_LIMIT: Final[int] = 1000
_LAST_MESSAGE_PREVIEW_LIMIT: Final[int] = 80


# ---------------------------------------------------------------------------
# Case model
# ---------------------------------------------------------------------------


class Case(BaseModel):
    """Persisted case record.

    `id` is a canonical UUID string (the API layer validates UUID format
    before this is reached). `model_history` is the LLM-bound history —
    raw `ModelMessage` objects carrying `ToolCallPart`/`ToolReturnPart`
    payloads across turns (ISSUE-M3-001). The wire `chat_history` is for
    the UI; `model_history` is for the LLM.

    The JSON round-trip degrades `ToolReturnPart.content` to a `dict`
    (ISSUE-USR-016), but the `ModelMessage` structure itself is preserved
    via the Pydantic `kind` discriminator.
    """

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    response_style: ResponseStyle
    icon_name: IconName
    is_demo: bool = False
    chat_history: list[ChatMessage] = []
    model_history: list[ModelMessage] = []


# ---------------------------------------------------------------------------
# Path containment helper (ISSUE-USR-001)
# ---------------------------------------------------------------------------


def _resolve_under(case_id: str, cases_path: Path) -> Path:
    """Build `{cases_path}/{case_id}.json` and verify it stays contained.

    Returns the resolved final path. Raises `ValueError` if the constructed
    path escapes `cases_path` (e.g. `../../etc/passwd` or `/etc/passwd`).
    """
    file_path = cases_path / f"{case_id}.json"
    if not file_path.resolve().is_relative_to(cases_path.resolve()):
        raise ValueError(
            f"case_id {case_id!r} resolves outside cases_path {cases_path!r}"
        )
    return file_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load(case_id: str, *, cases_path: Path) -> Case | None:
    """Load a case from `{cases_path}/{case_id}.json`.

    Returns `None` if the file does not exist (a soft "not found" rather
    than an exception, so the service layer can treat missing files as
    "start a new case" without try/except).
    """
    file_path = _resolve_under(case_id, cases_path)
    if not file_path.exists():
        return None
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return Case.model_validate(raw)


def save(case: Case, *, cases_path: Path) -> None:
    """Atomically write a case to `{cases_path}/{case.id}.json`.

    Creates the parent directory if it does not exist (ISSUE-005). Writes
    to a unique same-directory temp file, then `os.replace()`s it onto the
    final path. Cleans up the temp file in `finally` on any failure.
    """
    file_path = _resolve_under(case.id, cases_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = cases_path / f".{case.id}.{uuid4().hex}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(case.model_dump_json(indent=2))
            f.flush()
        os.replace(tmp_path, file_path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def delete(case_id: str, *, cases_path: Path) -> bool:
    """Delete `{cases_path}/{case_id}.json`.

    Returns `True` if the file was deleted, `False` if it did not exist.
    Does not raise on missing files — the service layer treats "not found"
    as a no-op.
    """
    file_path = _resolve_under(case_id, cases_path)
    if not file_path.exists():
        return False
    file_path.unlink()
    return True


def list_all(*, cases_path: Path) -> list[CaseSummary]:
    """Return a `CaseSummary` for every `{case_id}.json` file.

    For <1000 case files this is fast enough; no index file is needed.
    Logs an INFO warning when the file count exceeds 500 (ISSUE-DS-007).
    Files not matching `*.json` (e.g. leftover `.tmp` files from a crashed
    save) are ignored.
    """
    if not cases_path.exists():
        return []

    json_files = sorted(p for p in cases_path.iterdir() if p.suffix == ".json")
    if len(json_files) > _LIST_ALL_INFO_THRESHOLD:
        logger.info(
            "cases.list_all: %d files in %s (soft threshold %d); "
            "consider an index for >%d cases",
            len(json_files),
            cases_path,
            _LIST_ALL_INFO_THRESHOLD,
            _LIST_ALL_DOC_LIMIT,
        )

    summaries: list[CaseSummary] = []
    for file_path in json_files:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        case = Case.model_validate(raw)
        summaries.append(_to_summary(case))
    return summaries


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_summary(case: Case) -> CaseSummary:
    """Build a `CaseSummary` from a persisted `Case`.

    `last_message` is derived from the last assistant `ChatMessage`,
    preferring `step_content` (the structured analysis) over `text`
    (the raw agent output). Truncated to 80 chars.

    `tag_text` precedence: deadline > template_letter > None.
    """
    return CaseSummary(
        id=UUID(case.id),
        title=case.title,
        created_at=case.created_at,
        updated_at=case.updated_at,
        last_message=_derive_last_message(case.chat_history),
        icon_name=case.icon_name,
        response_style=case.response_style,
        tag_text=_derive_tag_text(case.chat_history),
        is_demo=case.is_demo,
    )


def _derive_last_message(history: list[ChatMessage]) -> str:
    """Return the last assistant message preview, truncated to 80 chars.

    Prefers `step_content` (structured analysis) when set and non-empty;
    falls back to `text`. Returns "" if no assistant message exists.
    """
    for msg in reversed(history):
        if msg.sender != "assistant":
            continue
        preview = (msg.step_content or "").strip() or msg.text
        return preview[:_LAST_MESSAGE_PREVIEW_LIMIT]
    return ""


def _derive_tag_text(history: list[ChatMessage]) -> str | None:
    """Return the rightmost tag for the case based on the last assistant turn.

    Precedence: deadline > template_letter > None. The last assistant message
    wins (consistent with `last_message`).
    """
    for msg in reversed(history):
        if msg.sender != "assistant":
            continue
        if msg.deadline is not None:
            return "Prazo calculado"
        if msg.template_letter:
            return "Mensagem pronta"
        return None
    return None


__all__ = [
    "Case",
    "delete",
    "list_all",
    "load",
    "save",
    "_to_summary",
    "_derive_last_message",
    "_derive_tag_text",
]
