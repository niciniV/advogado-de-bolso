from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from advogado_de_bolso.config import Settings
from advogado_de_bolso.deps import Deps
from advogado_de_bolso.tools.revisor import RevisionResult


@pytest.fixture
def settings() -> Settings:
    return Settings(
        GOOGLE_API_KEY="test-gcp-key",
        GEMINI_API_KEY="test-gemini-key",
        LLM_MODEL="test-model",
        THINKING_LEVEL="",
        DATA_PATH="./data/raw",
        CHROMA_PATH="./storage/chroma",
        COLLECTION_NAME="test_collection",
        RETRIEVAL_TOP_K=3,
        EMBEDDING_MODEL="test-embedding-model",
    )


@pytest.fixture
def mock_retriever():
    retriever = MagicMock()
    retriever.aretrieve = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def deps(settings, mock_retriever) -> Deps:
    return Deps(
        settings=settings,
        retriever=mock_retriever,
    )


@pytest.fixture
def ctx(deps) -> MagicMock:
    """Mock RunContext for tool tests.

    NOTE: ctx.model is mocked as a string ("google-gla:test-model").
    In production, this is a pydantic_ai.models.Model instance. This is
    acceptable for unit tests where the model is only passed through
    (e.g., to sub-agents), but integration tests should use a real
    Model instance.
    """
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    ctx.model = "google-gla:test-model"
    return ctx


@pytest.fixture
def mock_agent_run() -> MagicMock:
    result = MagicMock()
    result.output = "texto gerado pelo agente mockado"
    return result


@pytest.fixture
def mock_revision_result_approved() -> RevisionResult:
    return RevisionResult(
        needs_revision=False,
        issues=[],
        suggestions=[],
        approved_as_is=True,
    )


@pytest.fixture
def mock_revision_result_needs_fix() -> RevisionResult:
    return RevisionResult(
        needs_revision=True,
        issues=["Prazo incorreto: art. 26 diz 90 dias para duraveis"],
        suggestions=["Alterar prazo para 90 dias conforme CDC art. 26"],
        approved_as_is=False,
    )


@pytest.fixture
def sample_data_aquisicao() -> str:
    return "2025-01-15"


@pytest.fixture
def sample_data_compra() -> str:
    return "2025-06-01"
