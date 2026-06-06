from __future__ import annotations

import pytest
from pydantic import ValidationError

from advogado_de_bolso.tools.revisor import RevisionResult


class TestRevisionResultDefaults:
    def test_needs_revision_default_false(self):
        r = RevisionResult()
        assert r.needs_revision is False

    def test_issues_default_empty(self):
        r = RevisionResult()
        assert r.issues == []

    def test_suggestions_default_empty(self):
        r = RevisionResult()
        assert r.suggestions == []

    def test_approved_as_is_default_true(self):
        r = RevisionResult()
        assert r.approved_as_is is True


class TestRevisionResultCreation:
    def test_create_with_all_fields(self):
        r = RevisionResult(
            needs_revision=True,
            issues=["Erro juridico"],
            suggestions=["Corrigir artigo"],
            approved_as_is=False,
        )
        assert r.needs_revision is True
        assert r.issues == ["Erro juridico"]
        assert r.suggestions == ["Corrigir artigo"]
        assert r.approved_as_is is False

    def test_approved_as_is_true_leaves_issues_empty(self):
        r = RevisionResult(needs_revision=False, approved_as_is=True)
        assert r.approved_as_is is True
        assert r.needs_revision is False

    def test_issues_and_suggestions_are_string_lists(self):
        r = RevisionResult(
            issues=["Problema A", "Problema B"],
            suggestions=["Sugestao A", "Sugestao B"],
        )
        assert len(r.issues) == 2
        assert len(r.suggestions) == 2


class TestRevisionResultValidation:
    def test_needs_revision_must_be_bool(self):
        with pytest.raises(ValidationError):
            RevisionResult(needs_revision="sim")  # type: ignore[arg-type]

    def test_approved_as_is_must_be_bool(self):
        with pytest.raises(ValidationError):
            RevisionResult(approved_as_is="maybe")  # type: ignore[arg-type]


class TestRevisionResultEdgeCases:
    def test_approved_as_is_without_revision(self):
        r = RevisionResult(needs_revision=False, approved_as_is=True)
        assert r.approved_as_is is True
        assert r.needs_revision is False

    def test_issues_without_suggestions(self):
        r = RevisionResult(
            needs_revision=True,
            issues=["Problema encontrado"],
            suggestions=[],
        )
        assert len(r.issues) == 1
        assert r.suggestions == []

    def test_explicit_needs_revision_true(self):
        r = RevisionResult(needs_revision=True, issues=["Erro"])
        assert r.needs_revision is True
        assert r.issues == ["Erro"]
