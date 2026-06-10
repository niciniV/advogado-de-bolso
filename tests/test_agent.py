from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from advogado_de_bolso.agent import build_agent
from advogado_de_bolso.config import Settings


def test_build_agent_applies_preferred_configured_google_key() -> None:
    settings = Settings(
        GOOGLE_API_KEY="old-key",
        GEMINI_API_KEY="preferred-key",
        THINKING_LEVEL="",
    )

    with (
        patch.dict(os.environ, {"GOOGLE_API_KEY": "environment-key"}),
        patch("advogado_de_bolso.agent.Agent", return_value=MagicMock()),
    ):
        build_agent(settings)
        assert os.environ["GOOGLE_API_KEY"] == "preferred-key"
