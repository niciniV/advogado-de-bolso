from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from advogado_de_bolso.config import VALID_THINKING_LEVELS, Settings


class TestSettingsDefaults:
    def test_default_llm_model(self):
        s = Settings()
        assert s.llm_model == "gemma-4-31b-it"

    def test_default_retrieval_top_k(self):
        s = Settings()
        assert s.retrieval_top_k == 5

    def test_default_thinking_level(self):
        s = Settings()
        assert s.thinking_level == "HIGH"

    @pytest.mark.parametrize("value", [0, -1, 51])
    def test_retrieval_top_k_is_bounded(self, value: int):
        with pytest.raises(ValidationError):
            Settings(RETRIEVAL_TOP_K=value)


class TestThinkingLevelValidation:
    @pytest.mark.parametrize("level", VALID_THINKING_LEVELS)
    def test_valid_thinking_levels(self, level: str):
        s = Settings(THINKING_LEVEL=level)
        assert s.thinking_level == level

    @pytest.mark.parametrize("invalid", ["invalid", "LOWEST", "123"])
    def test_invalid_thinking_level_raises(self, invalid: str):
        with pytest.raises(ValidationError):
            Settings(THINKING_LEVEL=invalid)

    def test_empty_thinking_level_disables_thinking(self):
        s = Settings(THINKING_LEVEL="")
        assert s.google_thinking_config is None


class TestGoogleThinkingConfig:
    def test_with_valid_level(self):
        s = Settings(THINKING_LEVEL="HIGH")
        assert s.google_thinking_config == {"thinking_level": "HIGH"}

    def test_empty_level_is_none(self):
        s = Settings(THINKING_LEVEL="")
        assert s.google_thinking_config is None


class TestResolvedApiKey:
    def test_gemini_takes_priority(self):
        s = Settings(GOOGLE_API_KEY="gcp-key", GEMINI_API_KEY="gemini-key")
        assert s.resolved_google_api_key == "gemini-key"

    def test_fallback_to_google(self):
        s = Settings(GOOGLE_API_KEY="gcp-key", GEMINI_API_KEY="")
        assert s.resolved_google_api_key == "gcp-key"

    def test_empty_when_none_provided(self):
        s = Settings(GOOGLE_API_KEY="", GEMINI_API_KEY="")
        assert s.resolved_google_api_key == ""


class TestLLMProvider:
    def test_default_provider_is_google(self):
        s = Settings()
        assert s.llm_provider == "google"

    def test_full_model_name(self):
        s = Settings(LLM_MODEL="gemma-4-31b-it", LLM_PROVIDER="google")
        assert s.full_model_name == "google:gemma-4-31b-it"

    def test_full_model_name_custom_provider(self):
        s = Settings(LLM_MODEL="gpt-4", LLM_PROVIDER="openai")
        assert s.full_model_name == "openai:gpt-4"


class TestBuildModelSettingsProviderAware:
    def test_returns_none_for_non_google_provider(self):
        s = Settings(LLM_PROVIDER="openai", THINKING_LEVEL="HIGH")
        assert s.build_model_settings() is None


class TestBuildModelSettings:
    def test_returns_none_when_no_thinking(self):
        s = Settings(THINKING_LEVEL="")
        assert s.build_model_settings() is None

    @patch("pydantic_ai.models.google.GoogleModelSettings")
    def test_returns_settings_with_thinking(self, MockGoogleSettings):
        MockGoogleSettings.return_value = "mocked-google-settings"
        s = Settings(THINKING_LEVEL="HIGH")
        result = s.build_model_settings()
        assert result == "mocked-google-settings"
        MockGoogleSettings.assert_called_once_with(
            google_thinking_config={"thinking_level": "HIGH"}
        )
