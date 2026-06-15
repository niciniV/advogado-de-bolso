"""Golden tests for the structured-response adapter (batch 2).

These tests cover the wire-schema contract and the adapter dispatch logic
that the service layer will use in batch 4. They pin the behavior of:

  - `extract_structured_response()` — the main entrypoint.
  - The 3 helper functions: `_extract_questions`, `_extract_suggestive_text`,
    `_derive_quick_replies`.
  - The `tool_plain` raw-object round-trip through real Pydantic AI tool
    execution (pins `isinstance(part.content, DeadlineResult)` on the actual
    `ToolReturnPart` produced by the agent).

References
----------
- `.opencode/plans/02-schemas.md` (wire-type spec)
- `.opencode/plans/03-adapter.md` (adapter + helpers)
- `.opencode/plans/15-backend-tests.md` (this file's spec)
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.test import TestModel

from advogado_de_bolso.adapter import (
    _DEADLINE_QUICK_REPLIES,
    _DEFAULT_QUICK_REPLIES,
    _DOC_QUICK_REPLIES,
    _derive_quick_replies,
    _extract_questions,
    _extract_suggestive_text,
    extract_structured_response,
)
from advogado_de_bolso.contracts import (
    DeadlineResult,
    DraftedDocument,
    KnowledgeChunk,
)
from advogado_de_bolso.schemas import (
    CaseResponse,
    CaseSummary,
    ChatMessage,
    StructuredChatRequest,
    StructuredChatResponse,
    UpdateCaseRequest,
)

# ---------------------------------------------------------------------------
# Helpers for constructing ToolReturnPart objects in tests
# ---------------------------------------------------------------------------


def _tool_return(tool_name: str, content: object) -> ToolReturnPart:
    """Build a `ToolReturnPart` with the given tool name + raw content.

    The adapter dispatches on `part.content` via `isinstance`. This mirrors
    how Pydantic AI stores tool returns on the in-memory message history
    (per the `BaseToolReturnPart.content: ToolReturnContent` annotation).
    """
    return ToolReturnPart(tool_name=tool_name, content=cast(object, content))


def _deadline() -> DeadlineResult:
    return DeadlineResult(
        tipo_prazo="arrependimento",
        data_inicio=date(2025, 6, 1),
        data_limite=date(2025, 6, 8),
        dias=7,
        base_legal="CDC art. 49",
        item_label=None,
        vicio_oculto=False,
        nota="Use a data de recebimento do produto ou da contratacao do servico.",
    )


def _doc() -> DraftedDocument:
    return DraftedDocument(
        tipo="reclamacao_procon",
        tom="formal",
        destinatario="PROCON",
        texto="Senhor(a), venho por meio desta reclamar...",
    )


# ===========================================================================
# `schemas.py` — wire types
# ===========================================================================


class TestStructuredChatRequest:
    def test_minimal_request_accepts_message_only(self) -> None:
        req = StructuredChatRequest(message="Ola")
        assert req.message == "Ola"
        assert req.session_id is None
        assert req.response_style is None
        assert req.title is None
        assert req.icon_name is None

    def test_message_is_stripped(self) -> None:
        req = StructuredChatRequest(message="  Ola  ")
        assert req.message == "Ola"

    def test_blank_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="   ")

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="")

    def test_over_8000_char_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="a" * 8001)

    def test_exactly_8000_char_message_accepted(self) -> None:
        req = StructuredChatRequest(message="a" * 8000)
        assert len(req.message) == 8000

    def test_session_id_accepts_uuid_string(self) -> None:
        uid = "12345678-1234-5678-1234-567812345678"
        req = StructuredChatRequest(message="Ola", session_id=uid)
        assert req.session_id == UUID(uid)

    def test_session_id_accepts_uuid_object(self) -> None:
        uid = UUID("12345678-1234-5678-1234-567812345678")
        req = StructuredChatRequest(message="Ola", session_id=uid)
        assert req.session_id == uid

    def test_session_id_rejects_non_uuid_string(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="Ola", session_id="not-a-uuid")

    def test_title_is_stripped_and_bounded(self) -> None:
        req = StructuredChatRequest(message="Ola", title="  Hello  ")
        assert req.title == "Hello"
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="Ola", title="   ")
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="Ola", title="x" * 121)

    def test_title_max_length_120_accepted(self) -> None:
        req = StructuredChatRequest(message="Ola", title="x" * 120)
        assert req.title == "x" * 120

    def test_icon_name_accepts_known_values(self) -> None:
        for icon in ("shopping_bag", "receipt_long", "local_shipping", "gavel"):
            req = StructuredChatRequest(message="Ola", icon_name=icon)
            assert req.icon_name == icon

    def test_icon_name_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="Ola", icon_name="unknown")

    def test_response_style_accepts_known_values(self) -> None:
        for style in ("simples", "detalhado", "firme"):
            req = StructuredChatRequest(message="Ola", response_style=style)
            assert req.response_style == style

    def test_response_style_rejects_unknown(self) -> None:
        with pytest.raises(ValidationError):
            StructuredChatRequest(message="Ola", response_style="verbose")


class TestStructuredChatResponse:
    def test_default_construction_succeeds(self) -> None:
        """The adapter constructs a `StructuredChatResponse` BEFORE the service
        has appended the current turn. The `updated_at` and `chat_history`
        fields MUST have assembly-safe defaults so the response object can be
        built (ISSUE-USR-015)."""
        resp = StructuredChatResponse(
            step_title="X",
            step_content="Y",
        )
        assert resp.session_id == ""
        assert resp.updated_at is not None
        assert resp.chat_history == []
        assert resp.relevant_title == ""
        assert resp.relevant_content == ""
        assert resp.deadline is None
        assert resp.questions == []
        assert resp.suggestive_text is None
        assert resp.template_letter is None
        assert resp.quick_replies == []
        assert resp.blocked is False
        assert resp.blocked_message is None

    def test_updated_at_default_is_close_to_utcnow(self) -> None:
        before = datetime.now(UTC)
        resp = StructuredChatResponse(step_title="X", step_content="Y")
        after = datetime.now(UTC)
        assert before <= resp.updated_at <= after

    def test_updated_at_has_utc_tzinfo(self) -> None:
        resp = StructuredChatResponse(step_title="X", step_content="Y")
        assert resp.updated_at.tzinfo is not None
        assert resp.updated_at.utcoffset() == UTC.utcoffset(resp.updated_at)

    def test_chat_history_default_is_empty_list(self) -> None:
        resp = StructuredChatResponse(step_title="X", step_content="Y")
        assert resp.chat_history == []


class TestCaseSummary:
    def test_minimal_summary(self) -> None:
        summary = CaseSummary(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            title="X",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 2, tzinfo=UTC),
            last_message="Last line",
            icon_name="gavel",
            response_style="detalhado",
            is_demo=False,
        )
        assert summary.tag_text is None  # optional, default None

    def test_tag_text_can_be_set(self) -> None:
        summary = CaseSummary(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            title="X",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 2, tzinfo=UTC),
            last_message="Last",
            icon_name="gavel",
            response_style="detalhado",
            is_demo=False,
            tag_text="Prazo calculado",
        )
        assert summary.tag_text == "Prazo calculado"


class TestCaseResponse:
    def test_round_trip(self) -> None:
        case = CaseResponse(
            id=UUID("12345678-1234-5678-1234-567812345678"),
            title="X",
            created_at=datetime(2025, 1, 1, tzinfo=UTC),
            updated_at=datetime(2025, 1, 2, tzinfo=UTC),
            icon_name="gavel",
            response_style="detalhado",
            chat_history=[],
        )
        assert case.chat_history == []


class TestChatMessage:
    def test_user_message(self) -> None:
        msg = ChatMessage(id="user-1", sender="user", text="oi", timestamp=1718400000000)
        assert msg.timestamp == 1718400000000
        assert msg.sender == "user"

    def test_assistant_message_optional_fields(self) -> None:
        msg = ChatMessage(
            id="assistant-1",
            sender="assistant",
            text="response",
            timestamp=1718400000001,
            step_title="Title",
            step_content="Content",
        )
        assert msg.deadline is None
        assert msg.questions == []
        assert msg.relevant_title == ""
        assert msg.relevant_content == ""
        assert msg.template_letter is None
        assert msg.quick_replies == []


class TestUpdateCaseRequest:
    def test_single_field_accepted(self) -> None:
        for body, attrs in [
            ({"title": "X"}, {"title": "X"}),
            ({"icon_name": "shopping_bag"}, {"icon_name": "shopping_bag"}),
            ({"response_style": "simples"}, {"response_style": "simples"}),
        ]:
            req = UpdateCaseRequest.model_validate(body)
            for k, v in attrs.items():
                assert getattr(req, k) == v

    def test_all_fields_accepted(self) -> None:
        req = UpdateCaseRequest.model_validate(
            {"title": "X", "icon_name": "gavel", "response_style": "firme"}
        )
        assert req.title == "X"
        assert req.icon_name == "gavel"
        assert req.response_style == "firme"

    def test_empty_body_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({})

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({"title": "X", "unknown": 1})

    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({"title": "   "})

    def test_over_length_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({"title": "x" * 121})

    def test_unknown_icon_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({"icon_name": "unknown"})

    def test_unknown_response_style_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateCaseRequest.model_validate({"response_style": "verbose"})


# ===========================================================================
# `adapter.py` — main dispatch
# ===========================================================================


class TestExtractStructuredResponse:
    def test_deadline_turn_populates_deadline(self) -> None:
        deadline = _deadline()
        result = extract_structured_response(
            "Analise do prazo.",
            [_tool_return("calcular_prazo_consumidor", deadline)],
        )
        assert result.deadline is deadline

    def test_doc_turn_populates_template_letter(self) -> None:
        doc = _doc()
        result = extract_structured_response(
            "Documento pronto.",
            [_tool_return("redigir_documento", doc)],
        )
        assert result.template_letter == doc.texto

    def test_both_deadline_and_doc_populated(self) -> None:
        deadline = _deadline()
        doc = _doc()
        result = extract_structured_response(
            "Ambos.",
            [
                _tool_return("calcular_prazo_consumidor", deadline),
                _tool_return("redigir_documento", doc),
            ],
        )
        assert result.deadline is deadline
        assert result.template_letter == doc.texto

    def test_empty_rag_returns_no_relevant_content(self) -> None:
        result = extract_structured_response(
            "Sem RAG.",
            [_tool_return("search_knowledge_base", [])],
        )
        assert result.relevant_title == ""
        assert result.relevant_content == ""

    def test_rag_with_chunks_populates_relevant_title_and_content(self) -> None:
        chunks = [
            KnowledgeChunk(fonte="CDC.txt", texto="Art. 26 texto A."),
            KnowledgeChunk(fonte="STJ.txt", texto="Sumula 469 texto B."),
        ]
        result = extract_structured_response(
            "Com RAG.",
            [_tool_return("search_knowledge_base", chunks)],
        )
        assert result.relevant_title == "CDC.txt"
        assert "Art. 26 texto A." in result.relevant_content
        assert "Sumula 469 texto B." in result.relevant_content
        assert "Art. 26 texto A." in result.relevant_content
        # second chunk separator
        assert "\n\n" in result.relevant_content

    def test_rag_with_more_than_two_chunks_truncates_to_two(self) -> None:
        chunks = [
            KnowledgeChunk(fonte="a.txt", texto="A"),
            KnowledgeChunk(fonte="b.txt", texto="B"),
            KnowledgeChunk(fonte="c.txt", texto="C"),
        ]
        result = extract_structured_response(
            "Prose.",
            [_tool_return("search_knowledge_base", chunks)],
        )
        assert result.relevant_title == "a.txt"
        assert "A" in result.relevant_content
        assert "B" in result.relevant_content
        assert "C" not in result.relevant_content

    def test_rag_tuple_accepted_as_sequence(self) -> None:
        """ISSUE-M3-010: a tuple from the tool should be accepted by the
        adapter (Pydantic AI's `ToolReturnContent` is a Sequence-or-Mapping-or-Any)."""
        chunks = (
            KnowledgeChunk(fonte="x.txt", texto="conteudo x"),
            KnowledgeChunk(fonte="y.txt", texto="conteudo y"),
        )
        result = extract_structured_response(
            "Prose.",
            [_tool_return("search_knowledge_base", chunks)],
        )
        assert result.relevant_title == "x.txt"
        assert "conteudo x" in result.relevant_content
        assert "conteudo y" in result.relevant_content

    def test_deadline_tool_returning_string_does_not_crash(self) -> None:
        """The tool's error path returns a plain `str`. The adapter must
        ignore it (no crash, `deadline` stays None)."""
        result = extract_structured_response(
            "Prose.",
            [_tool_return("calcular_prazo_consumidor", "informe o tipo de item")],
        )
        assert result.deadline is None

    def test_blocked_response_sets_blocked_and_message(self) -> None:
        result = extract_structured_response(
            "Prose.",
            [],
            blocked=True,
            blocked_message="Resposta bloqueada: citacao legal incorreta.",
        )
        assert result.blocked is True
        assert result.blocked_message == "Resposta bloqueada: citacao legal incorreta."

    def test_unblocked_response_has_blocked_false(self) -> None:
        result = extract_structured_response("Prose.", [])
        assert result.blocked is False
        assert result.blocked_message is None

    def test_unknown_tool_name_logs_warning_and_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ISSUE-DS-006: an unknown tool name is logged at WARNING and the
        adapter does not raise (fail-soft)."""
        with caplog.at_level(logging.WARNING, logger="advogado_de_bolso.adapter"):
            result = extract_structured_response(
                "Prose.",
                [_tool_return("some_future_tool", {"future": "thing"})],
            )
        # response built without raising
        assert result.step_title  # some non-empty title from the prose
        # WARNING was emitted
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("some_future_tool" in r.getMessage() for r in warnings)

    def test_mismatched_tool_name_for_deadline_is_ignored(self) -> None:
        """Even if the content is a `DeadlineResult`, if the tool name is
        not the deadline tool, the adapter must NOT pick it up. Dispatch is
        by tool_name, not by type alone (per `extract_structured_response` spec)."""
        deadline = _deadline()
        result = extract_structured_response(
            "Prose.",
            [_tool_return("other_tool", deadline)],
        )
        assert result.deadline is None

    def test_mismatched_tool_name_for_doc_is_ignored(self) -> None:
        doc = _doc()
        result = extract_structured_response(
            "Prose.",
            [_tool_return("other_tool", doc)],
        )
        assert result.template_letter is None

    def test_deadline_content_in_non_deadline_tool_does_not_crash(self) -> None:
        """If a tool returns a string and the dispatch name is wrong,
        the adapter should silently ignore it (not crash)."""
        result = extract_structured_response(
            "Prose.",
            [_tool_return("not_deadline", "some string error")],
        )
        assert result.deadline is None

    def test_returned_response_has_default_session_id(self) -> None:
        """The service layer fills in session_id; the adapter writes ""."""
        result = extract_structured_response("Prose.", [])
        assert result.session_id == ""


# ===========================================================================
# `adapter.py` — prose -> step_title, step_content
# ===========================================================================


class TestProseToStep:
    def test_step_title_is_first_line_of_prose(self) -> None:
        result = extract_structured_response("Title line\nBody line", [])
        assert result.step_title == "Title line"

    def test_step_content_is_rest_of_prose(self) -> None:
        result = extract_structured_response("Title line\nBody line", [])
        assert "Body line" in result.step_content

    def test_two_paragraph_split(self) -> None:
        # `split("\n\n", 1)` yields 2 elements: paragraphs[0] (which seeds
        # `step_title` from its first line) and paragraphs[1] (the rest).
        # So `step_title == "Title"` (first line of paragraphs[0]) and
        # `step_content == "Para 2"` (paragraphs[1] only). "Para 1" lives
        # in paragraphs[0] and is consumed as part of the title source.
        result = extract_structured_response("Title\nPara 1\n\nPara 2", [])
        assert result.step_title == "Title"
        assert result.step_content == "Para 2"

    def test_step_title_capped_at_120_chars(self) -> None:
        long_title = "A" * 200
        result = extract_structured_response(f"{long_title}\nBody", [])
        assert len(result.step_title) == 120

    def test_empty_prose_falls_back_to_initial_analysis(self) -> None:
        """ISSUE-004: empty prose must trigger the `Análise inicial`
        fallback rather than producing an empty `step_title`."""
        result = extract_structured_response("", [])
        assert result.step_title == "Análise inicial"
        assert result.step_content == ""

    def test_whitespace_only_prose_falls_back_to_initial_analysis(self) -> None:
        result = extract_structured_response("   \n\n  ", [])
        assert result.step_title == "Análise inicial"
        assert result.step_content == ""


# ===========================================================================
# `adapter.py` — question extraction
# ===========================================================================


class TestExtractQuestions:
    def test_no_questions_for_empty_prose(self) -> None:
        assert _extract_questions("") == []

    def test_no_questions_for_prose_with_no_patterns(self) -> None:
        assert _extract_questions("This prose has no questions at all.") == []

    def test_numbered_question_extracted(self) -> None:
        questions = _extract_questions("1. Qual a data?")
        assert "Qual a data?" in questions

    def test_numbered_question_preserves_full_text(self) -> None:
        # The spec test is "1. The customer should..." (no `?`) which
        # must NOT be picked up as a question (ISSUE-USR-010). This test
        # exercises the non-question form to pin the regex fix.
        questions_no_q = _extract_questions("1. The customer should do X")
        assert "The customer should do X" not in questions_no_q

    def test_numbered_non_question_NOT_extracted(self) -> None:
        """ISSUE-USR-010: numbered items that DON'T end in "?" must NOT be
        picked up as questions (the previous regex was too greedy)."""
        questions = _extract_questions("1. The customer should...")
        assert questions == []

    def test_bullet_question_extracted(self) -> None:
        questions = _extract_questions("- Qual a data de compra?")
        assert "Qual a data de compra?" in questions

    def test_posso_question_extracted_full(self) -> None:
        """ISSUE-USR-010: the keyword alternatives are non-capturing, so
        the full question (not just "Posso") must be returned."""
        questions = _extract_questions("Posso cancelar a compra?")
        assert "Posso cancelar a compra?" in questions

    def test_posso_question_is_NOT_just_posso(self) -> None:
        questions = _extract_questions("Posso cancelar a compra?")
        # The bad behavior would be returning "Posso" only
        assert "Posso" not in questions

    def test_poderia_question_extracted_full(self) -> None:
        questions = _extract_questions("Poderia me explicar melhor?")
        assert "Poderia me explicar melhor?" in questions

    def test_pode_question_extracted_full(self) -> None:
        questions = _extract_questions("Pode me dar mais detalhes?")
        assert "Pode me dar mais detalhes?" in questions

    def test_consegue_question_extracted_full(self) -> None:
        questions = _extract_questions("Consegue revisar o prazo?")
        assert "Consegue revisar o prazo?" in questions

    def test_voce_poderia_question_extracted_full(self) -> None:
        # The spec regex uses the accented "Você poderia". With
        # `re.IGNORECASE` only case (not diacritics) is normalized, so
        # the input must use the exact same character set as the
        # alternative list in the regex.
        questions = _extract_questions("Você poderia revisar a data?")
        assert "Você poderia revisar a data?" in questions

    def test_keyword_alternatives_are_case_insensitive(self) -> None:
        questions = _extract_questions("posso cancelar a compra?")
        assert "posso cancelar a compra?" in questions

    def test_questions_are_capped_at_5(self) -> None:
        prose = "\n".join(
            [
                "1. A?",
                "2. B?",
                "3. C?",
                "4. D?",
                "5. E?",
                "6. F?",
                "7. G?",
            ]
        )
        questions = _extract_questions(prose)
        assert len(questions) == 5

    def test_questions_deduplicate(self) -> None:
        prose = "1. Qual a data?\n\nPosso cancelar a compra?\n\nPosso cancelar a compra?"
        questions = _extract_questions(prose)
        # "Posso cancelar a compra?" should appear at most once
        assert questions.count("Posso cancelar a compra?") <= 1

    def test_questions_rstrip_trailing_punctuation(self) -> None:
        """Helper rstrip's trailing '?. ' before re-appending '?'."""
        questions = _extract_questions("1. Qual a data?")
        # The helper appends a "?" if not already present
        for q in questions:
            assert q.endswith("?")


# ===========================================================================
# `adapter.py` — suggestive text extraction
# ===========================================================================


class TestExtractSuggestiveText:
    def test_none_for_empty_prose(self) -> None:
        assert _extract_suggestive_text("") is None

    def test_none_for_whitespace_prose(self) -> None:
        assert _extract_suggestive_text("   \n  ") is None

    def test_returns_last_non_empty_line(self) -> None:
        result = _extract_suggestive_text("Line 1\nLine 2\nLine 3")
        assert result == "Line 3"

    def test_returns_last_line_trimmed_to_200(self) -> None:
        long_line = "A" * 300
        result = _extract_suggestive_text(f"Line 1\n{long_line}")
        assert result is not None
        assert len(result) == 200

    def test_ignores_trailing_blank_lines(self) -> None:
        result = _extract_suggestive_text("Line 1\nLine 2\n   \n")
        assert result == "Line 2"


# ===========================================================================
# `adapter.py` — quick replies derivation
# ===========================================================================


class TestDeriveQuickReplies:
    def test_doc_chip_set_used_when_letter_present(self) -> None:
        result = _derive_quick_replies(None, "letter text")
        assert result == _DOC_QUICK_REPLIES

    def test_deadline_chip_set_used_when_deadline_present(self) -> None:
        deadline = _deadline()
        result = _derive_quick_replies(deadline, None)
        assert result == _DEADLINE_QUICK_REPLIES

    def test_default_chip_set_when_nothing(self) -> None:
        result = _derive_quick_replies(None, None)
        assert result == _DEFAULT_QUICK_REPLIES

    def test_doc_takes_precedence_over_deadline(self) -> None:
        """If both are present, doc wins (per the helper's `if/elif`)."""
        deadline = _deadline()
        result = _derive_quick_replies(deadline, "letter text")
        assert result == _DOC_QUICK_REPLIES

    def test_chip_lists_have_3_items_each(self) -> None:
        assert len(_DEFAULT_QUICK_REPLIES) == 3
        assert len(_DEADLINE_QUICK_REPLIES) == 3
        assert len(_DOC_QUICK_REPLIES) == 3


class TestQuickRepliesInResponse:
    def test_deadline_turn_uses_deadline_chips(self) -> None:
        deadline = _deadline()
        result = extract_structured_response(
            "Prose.",
            [_tool_return("calcular_prazo_consumidor", deadline)],
        )
        assert result.quick_replies == _DEADLINE_QUICK_REPLIES

    def test_doc_turn_uses_doc_chips(self) -> None:
        doc = _doc()
        result = extract_structured_response(
            "Prose.",
            [_tool_return("redigir_documento", doc)],
        )
        assert result.quick_replies == _DOC_QUICK_REPLIES

    def test_no_tool_turn_uses_default_chips(self) -> None:
        result = extract_structured_response("Prose.", [])
        assert result.quick_replies == _DEFAULT_QUICK_REPLIES


# ===========================================================================
# `adapter.py` — tool_plain raw-object contract
# ===========================================================================


class TestToolPlainRoundTrip:
    """Pins the in-memory `tool_plain` -> `ToolReturnPart` contract: when a
    `tool_plain`-decorated function returns a typed Pydantic object (not a
    string/dict), the agent's `result.new_messages()` must contain a
    `ModelRequest.parts[-1]` whose part is a `ToolReturnPart` whose
    `content` is `isinstance` of the typed object."""

    @pytest.mark.asyncio
    async def test_tool_plain_preserves_typed_return(self) -> None:
        """ISSUE-006 + ISSUE-USR-009: the real Pydantic AI tool-execution
        path must preserve the raw typed `DeadlineResult` object in
        `ToolReturnPart.content`. If Pydantic AI ever stringifies
        `tool_plain` returns, this test will fail loudly."""
        deadline = _deadline()

        def stub_calcular(tipo_prazo: str, data_inicio_prazo: str) -> DeadlineResult:
            return deadline

        test_model = TestModel(custom_output_text="Prazo calculado.")
        agent = Agent(model=test_model, system_prompt="stub")
        agent.tool_plain(stub_calcular)

        result = await agent.run("calcule um prazo")
        new_msgs = result.new_messages()

        # Find the ModelResponse that contains the ToolCallPart.
        call_index = -1
        for i, msg in enumerate(new_msgs):
            if isinstance(msg, ModelResponse) and any(
                isinstance(p, ToolCallPart) and p.tool_name == "stub_calcular"
                for p in msg.parts
            ):
                call_index = i
                break
        assert call_index >= 0, "expected a ModelResponse with a ToolCallPart"

        # The IMMEDIATELY-FOLLOWING message must be a ModelRequest whose
        # last part is a ToolReturnPart whose content is the raw typed
        # object (NOT a dict or stringified version).
        tool_return_msg = new_msgs[call_index + 1]
        assert isinstance(tool_return_msg, ModelRequest)
        tool_returns = [p for p in tool_return_msg.parts if isinstance(p, ToolReturnPart)]
        assert tool_returns, "expected a ToolReturnPart in the following ModelRequest"
        tr = next(p for p in tool_returns if p.tool_name == "stub_calcular")
        assert isinstance(tr.content, DeadlineResult), (
            f"tool_plain must preserve the raw typed object; "
            f"got {type(tr.content).__name__}"
        )
        assert tr.content.dias == 7

        # The agent then produces a final ModelResponse with the text.
        final = new_msgs[-1]
        assert isinstance(final, ModelResponse)
        assert any(isinstance(p, TextPart) for p in final.parts)

    @pytest.mark.asyncio
    async def test_tool_plain_return_passes_through_adapter(self) -> None:
        """End-to-end: `tool_plain` -> `new_messages()` -> adapter dispatch.

        The tool is named `calcular_prazo_consumidor` (the canonical
        production name) so the adapter's tool_name dispatch picks it up.
        """
        deadline = _deadline()

        def calcular_prazo_consumidor(
            tipo_prazo: str, data_inicio_prazo: str
        ) -> DeadlineResult:
            return deadline

        test_model = TestModel(custom_output_text="Ok.")
        agent = Agent(model=test_model, system_prompt="stub")
        agent.tool_plain(calcular_prazo_consumidor)

        result = await agent.run("calcule")
        new_msgs = result.new_messages()

        # Collect every ToolReturnPart.
        tool_returns: list[ToolReturnPart] = [
            p for m in new_msgs if isinstance(m, ModelRequest) for p in m.parts
            if isinstance(p, ToolReturnPart)
        ]
        assert tool_returns

        # Pull the final assistant text as the prose.
        prose_candidates = [
            str(p.content)
            for m in new_msgs
            if isinstance(m, ModelResponse)
            for p in m.parts
            if isinstance(p, TextPart)
        ]
        prose = prose_candidates[-1] if prose_candidates else ""

        # Run the adapter — it MUST dispatch to the deadline branch.
        structured = extract_structured_response(prose, tool_returns)
        assert structured.deadline is not None
        assert structured.deadline.dias == 7
        assert structured.deadline.base_legal == "CDC art. 49"
