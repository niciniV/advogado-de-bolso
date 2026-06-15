"""Storage layer tests (batch 3).

Pins the behavior of `src/advogado_de_bolso/storage/cases.py`:
- Atomic write uses a unique same-directory `.tmp` path and `os.replace`; two
  concurrent saves never share a temp filename or produce malformed JSON.
- `delete` removes the file.
- `list_all` returns the right summaries, including truncated `last_message`
  and deterministic `tag_text` precedence (deadline > template_letter > None).
- Missing file -> `load` returns `None`, not raise.
- Path containment: passing a malicious `case_id` like `../../etc/passwd`
  raises `ValueError`.
- Atomic save creates the parent directory if missing.

References
----------
- `.opencode/plans/04-storage.md` — storage spec.
- `.opencode/plans/15-backend-tests.md` — this file's spec.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from advogado_de_bolso.contracts import DeadlineResult
from advogado_de_bolso.schemas import CaseSummary, ChatMessage
from advogado_de_bolso.storage import cases

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cases_path(tmp_path: Path) -> Path:
    """Per-test storage root (empty directory)."""
    p = tmp_path / "cases"
    p.mkdir()
    return p


def _now() -> datetime:
    return datetime.now(UTC)


def _make_case(
    case_id: str | None = None,
    *,
    title: str = "Test case",
    is_demo: bool = False,
    chat_history: list[ChatMessage] | None = None,
    model_history: list[ModelMessage] | None = None,
) -> cases.Case:
    cid = case_id or str(uuid4())
    now = _now()
    return cases.Case(
        id=cid,
        title=title,
        created_at=now,
        updated_at=now,
        response_style="simples",
        icon_name="shopping_bag",
        is_demo=is_demo,
        chat_history=chat_history or [],
        model_history=model_history or [],
    )


# ---------------------------------------------------------------------------
# Case model
# ---------------------------------------------------------------------------


class TestCaseModel:
    def test_round_trip_preserves_model_history_structure(
        self, cases_path: Path
    ) -> None:
        """`model_history` survives the storage layer round-trip as proper
        `ModelMessage` objects (the `kind` discriminator carries through);
        the `ToolReturnPart.content` becomes a `dict` (ISSUE-USR-016) but
        the structured fields are still there.
        """
        deadline = DeadlineResult(
            tipo_prazo="arrependimento",
            data_inicio=datetime(2025, 6, 1),
            data_limite=datetime(2025, 6, 8),
            dias=7,
            base_legal="CDC art. 49",
            item_label=None,
            vicio_oculto=False,
            nota="Use a data de recebimento do produto ou da contratacao do servico.",
        )
        msgs: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="Posso cancelar?")]),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="calcular_prazo_consumidor",
                        args={"tipo_prazo": "arrependimento"},
                    ),
                ],
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="calcular_prazo_consumidor",
                        content=deadline,
                        tool_call_id="call_1",
                    ),
                ],
            ),
        ]
        case = _make_case(model_history=msgs)

        cases.save(case, cases_path=cases_path)
        loaded = cases.load(case.id, cases_path=cases_path)

        assert loaded is not None
        assert isinstance(loaded, cases.Case)
        assert len(loaded.model_history) == 3
        assert isinstance(loaded.model_history[0], ModelRequest)
        assert isinstance(loaded.model_history[1], ModelResponse)
        assert isinstance(loaded.model_history[2], ModelRequest)
        trp = loaded.model_history[2].parts[0]
        assert isinstance(trp, ToolReturnPart)
        # JSON round-trip degrades content to dict (ISSUE-USR-016)
        assert isinstance(trp.content, dict)
        assert trp.content["tipo_prazo"] == "arrependimento"
        assert trp.content["dias"] == 7
        assert trp.content["base_legal"] == "CDC art. 49"


# ---------------------------------------------------------------------------
# load / save
# ---------------------------------------------------------------------------


class TestLoadSave:
    def test_save_then_load_round_trip(self, cases_path: Path) -> None:
        case = _make_case(title="Round trip")
        cases.save(case, cases_path=cases_path)
        loaded = cases.load(case.id, cases_path=cases_path)
        assert loaded is not None
        assert loaded.id == case.id
        assert loaded.title == "Round trip"
        assert loaded.response_style == "simples"
        assert loaded.icon_name == "shopping_bag"
        assert loaded.is_demo is False
        assert loaded.chat_history == []

    def test_load_missing_file_returns_none(self, cases_path: Path) -> None:
        missing_id = str(uuid4())
        assert cases.load(missing_id, cases_path=cases_path) is None

    def test_save_persists_to_expected_path(self, cases_path: Path) -> None:
        case = _make_case()
        cases.save(case, cases_path=cases_path)
        assert (cases_path / f"{case.id}.json").exists()

    def test_save_overwrites_existing(self, cases_path: Path) -> None:
        case = _make_case(title="First")
        cases.save(case, cases_path=cases_path)
        case.title = "Second"
        cases.save(case, cases_path=cases_path)
        loaded = cases.load(case.id, cases_path=cases_path)
        assert loaded is not None
        assert loaded.title == "Second"

    def test_save_creates_parent_directory_if_missing(
        self, tmp_path: Path
    ) -> None:
        """ISSUE-005: `save()` calls `mkdir(parents=True, exist_ok=True)`
        before writing. The parent directory may not exist on first save.
        """
        nested = tmp_path / "a" / "b" / "c" / "cases"
        assert not nested.exists()
        case = _make_case()
        cases.save(case, cases_path=nested)
        assert nested.is_dir()
        assert (nested / f"{case.id}.json").exists()


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_delete_removes_file(self, cases_path: Path) -> None:
        case = _make_case()
        cases.save(case, cases_path=cases_path)
        assert (cases_path / f"{case.id}.json").exists()
        result = cases.delete(case.id, cases_path=cases_path)
        assert result is True
        assert not (cases_path / f"{case.id}.json").exists()

    def test_delete_missing_returns_false(self, cases_path: Path) -> None:
        result = cases.delete(str(uuid4()), cases_path=cases_path)
        assert result is False

    def test_delete_does_not_raise_for_missing(self, cases_path: Path) -> None:
        # Behavior contract: missing file is a soft "False" return, not an
        # exception. This matches `os.remove` unlink_file semantics used by
        # the service layer.
        cases.delete(str(uuid4()), cases_path=cases_path)  # does not raise


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


def _assistant_message(
    text: str = "Default text",
    *,
    step_content: str | None = None,
    deadline: DeadlineResult | None = None,
    template_letter: str | None = None,
) -> ChatMessage:
    return ChatMessage(
        id=str(uuid4()),
        sender="assistant",
        text=text,
        timestamp=1,
        step_content=step_content,
        deadline=deadline,
        template_letter=template_letter,
    )


def _user_message(text: str = "hi") -> ChatMessage:
    return ChatMessage(
        id=str(uuid4()),
        sender="user",
        text=text,
        timestamp=1,
    )


class TestListAll:
    def test_empty_directory_returns_empty_list(self, cases_path: Path) -> None:
        assert cases.list_all(cases_path=cases_path) == []

    def test_returns_one_summary_per_file(self, cases_path: Path) -> None:
        ids = [str(uuid4()) for _ in range(3)]
        for cid in ids:
            cases.save(_make_case(case_id=cid), cases_path=cases_path)
        summaries = cases.list_all(cases_path=cases_path)
        assert len(summaries) == 3
        assert {s.id for s in summaries} == {UUID(i) for i in ids}

    def test_summary_uses_case_id_as_uuid(self, cases_path: Path) -> None:
        cid = str(uuid4())
        cases.save(_make_case(case_id=cid), cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert isinstance(summary.id, UUID)
        assert summary.id == UUID(cid)

    def test_summary_preserves_title_and_flags(self, cases_path: Path) -> None:
        cid = str(uuid4())
        cases.save(
            _make_case(case_id=cid, title="Demo", is_demo=True),
            cases_path=cases_path,
        )
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.title == "Demo"
        assert summary.is_demo is True
        assert summary.icon_name == "shopping_bag"
        assert summary.response_style == "simples"

    def test_last_message_uses_step_content_when_present(
        self, cases_path: Path
    ) -> None:
        long_step = "x" * 200
        history = [
            _user_message("user1"),
            _assistant_message(text="fallback text", step_content=long_step),
        ]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        # Truncated to 80 chars (no ellipsis per spec)
        assert summary.last_message == long_step[:80]
        assert len(summary.last_message) == 80

    def test_last_message_falls_back_to_text_when_step_content_missing(
        self, cases_path: Path
    ) -> None:
        history = [
            _user_message("user1"),
            _assistant_message(text="Fallback text only", step_content=None),
        ]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.last_message == "Fallback text only"

    def test_last_message_ignores_user_messages(self, cases_path: Path) -> None:
        history = [
            _user_message("user's last message"),
            _assistant_message(text="assistant's first"),
        ]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        # Uses the assistant message, not the user's
        assert summary.last_message == "assistant's first"

    def test_last_message_empty_when_no_assistant_message(
        self, cases_path: Path
    ) -> None:
        history = [_user_message("only a user message")]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.last_message == ""

    def test_tag_text_deadline_takes_precedence(self, cases_path: Path) -> None:
        deadline = DeadlineResult(
            tipo_prazo="arrependimento",
            data_inicio=datetime(2025, 6, 1),
            data_limite=datetime(2025, 6, 8),
            dias=7,
            base_legal="CDC art. 49",
            item_label=None,
            vicio_oculto=False,
            nota="n",
        )
        history = [
            _assistant_message(
                text="x",
                deadline=deadline,
                template_letter="Some letter",
            ),
        ]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.tag_text == "Prazo calculado"

    def test_tag_text_template_letter_when_no_deadline(
        self, cases_path: Path
    ) -> None:
        history = [
            _assistant_message(
                text="x", deadline=None, template_letter="Some letter"
            ),
        ]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.tag_text == "Mensagem pronta"

    def test_tag_text_none_when_neither(self, cases_path: Path) -> None:
        history = [_assistant_message(text="x")]
        case = _make_case(chat_history=history)
        cases.save(case, cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert summary.tag_text is None

    def test_returns_case_summary_instances(self, cases_path: Path) -> None:
        cases.save(_make_case(), cases_path=cases_path)
        [summary] = cases.list_all(cases_path=cases_path)
        assert isinstance(summary, CaseSummary)


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------


class TestPathContainment:
    def test_path_traversal_raises_value_error(self, cases_path: Path) -> None:
        """ISSUE-USR-001: every storage function constructs
        `cases_path / f"{case_id}.json"` and rejects any case_id that escapes
        the `cases_path` root.
        """
        with pytest.raises(ValueError):
            cases.load("../../etc/passwd", cases_path=cases_path)
        with pytest.raises(ValueError):
            cases.save(_make_case(case_id="../../etc/passwd"), cases_path=cases_path)
        with pytest.raises(ValueError):
            cases.delete("../../etc/passwd", cases_path=cases_path)

    def test_absolute_path_raises_value_error(self, cases_path: Path) -> None:
        """A `case_id` starting with a separator is treated as absolute and
        escapes the cases_path root (Path.__truediv__ discards the left
        operand when the right is absolute).
        """
        with pytest.raises(ValueError):
            cases.load("/etc/passwd", cases_path=cases_path)


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_save_uses_unique_temp_path(self, cases_path: Path) -> None:
        """The temp filename includes a uuid4 hex, so two concurrent saves
        of the same case use distinct temp files.
        """
        case = _make_case()
        tmp_files_seen: list[Path] = []
        real_replace = os.replace

        def spy_replace(src: str | bytes, dst: str | bytes) -> None:
            tmp_files_seen.append(Path(os.fsdecode(src) if isinstance(src, bytes) else src))
            real_replace(src, dst)

        with patch("os.replace", spy_replace):
            for _ in range(3):
                cases.save(case, cases_path=cases_path)

        assert len(tmp_files_seen) == 3
        # Distinct filenames
        names = {p.name for p in tmp_files_seen}
        assert len(names) == 3
        # All in the cases_path directory (not in /tmp or CWD)
        for p in tmp_files_seen:
            assert p.parent == cases_path
            # Matches the unique-temp pattern .{case_id}.{hex}.tmp
            assert p.name.startswith(f".{case.id}.")
            assert p.name.endswith(".tmp")

    def test_save_uses_os_replace(self, cases_path: Path) -> None:
        """Atomic semantics require `os.replace`, not `os.rename`.
        `os.rename` is not atomic on all filesystems and can fail on Windows
        if the destination exists.
        """
        case = _make_case()
        called_with: list[tuple[Path, Path]] = []
        real = os.replace

        def spy(src: str | bytes, dst: str | bytes) -> None:
            src_str = os.fsdecode(src) if isinstance(src, bytes) else src
            dst_str = os.fsdecode(dst) if isinstance(dst, bytes) else dst
            called_with.append((Path(src_str), Path(dst_str)))
            real(src, dst)

        with patch("os.replace", spy):
            cases.save(case, cases_path=cases_path)

        assert len(called_with) == 1
        src, dst = called_with[0]
        assert src.parent == cases_path
        assert dst == cases_path / f"{case.id}.json"

    def test_no_temp_file_remains_after_save(self, cases_path: Path) -> None:
        case = _make_case()
        cases.save(case, cases_path=cases_path)
        # No leftover .tmp files in cases_path
        tmp_files = [p for p in cases_path.iterdir() if p.name.endswith(".tmp")]
        assert tmp_files == []

    def test_concurrent_saves_produce_valid_json(
        self, cases_path: Path
    ) -> None:
        """Two threads saving the same case concurrently never produce
        malformed JSON or a torn file.

        The spec ("Atomic replacement prevents torn/partially-written JSON,
        but it does not prevent cross-process lost updates. Concurrent API
        + CLI read-modify-write operations on the same case are explicitly
        unsupported and use last-writer-wins semantics.") acknowledges that
        concurrent saves to the same case may race; the contract is that
        the file is never in a torn state. We therefore tolerate transient
        `PermissionError`s from the OS file-lock contention and assert the
        final on-disk state is a valid `Case`.
        """
        case = _make_case()
        barrier = threading.Barrier(4)

        def worker(payload_title: str) -> None:
            local = case.model_copy(update={"title": payload_title})
            barrier.wait(timeout=5)
            for _ in range(5):
                try:
                    cases.save(local, cases_path=cases_path)
                except (PermissionError, OSError):
                    # Windows can raise `PermissionError` when two threads
                    # race on the same target file (`os.replace` requires
                    # the target not to be in use). This is the expected
                    # "lost update" path; the previous write is still on
                    # disk intact.
                    continue

        threads = [
            threading.Thread(target=worker, args=(f"t{i}",)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # The final file is valid JSON and parses to a Case. The title is
        # one of the four worker titles (last-writer-wins).
        final = cases_path / f"{case.id}.json"
        assert final.exists()
        data = json.loads(final.read_text(encoding="utf-8"))
        loaded = cases.Case.model_validate(data)
        assert loaded.id == case.id
        assert loaded.title in {"t0", "t1", "t2", "t3"}

    def test_concurrent_saves_to_different_cases_succeed(
        self, cases_path: Path
    ) -> None:
        errors: list[BaseException] = []

        def worker(idx: int) -> None:
            try:
                local = _make_case(case_id=str(uuid4()), title=f"t{idx}")
                for _ in range(3):
                    cases.save(local, cases_path=cases_path)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        assert not errors
        # Each thread produced its own case file
        summaries = cases.list_all(cases_path=cases_path)
        assert len(summaries) == 6

    def test_temp_file_in_same_directory_as_final(
        self, cases_path: Path
    ) -> None:
        """The temp file is created in the same directory as the final file
        so `os.replace` is atomic on POSIX (different filesystems would break
        the atomicity guarantee).
        """
        case = _make_case()
        captured: list[Path] = []
        real = os.replace

        def spy(src: str | bytes, dst: str | bytes) -> None:
            src_str = os.fsdecode(src) if isinstance(src, bytes) else src
            captured.append(Path(src_str))
            real(src, dst)

        with patch("os.replace", spy):
            cases.save(case, cases_path=cases_path)

        [src] = captured
        assert src.parent == cases_path
