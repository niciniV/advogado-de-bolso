"""Configuracoes carregadas de variaveis de ambiente / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_THINKING_LEVELS: tuple[str, ...] = ("HIGH", "MEDIUM", "LOW", "MINIMAL")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    llm_model: str = Field(default="gemma-4-31b-it", alias="LLM_MODEL")
    llm_provider: str = Field(default="google", alias="LLM_PROVIDER")
    thinking_level: str = Field(default="HIGH", alias="THINKING_LEVEL")

    embedding_model: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL")

    data_path: Path = Field(default=Path("./data/raw"), alias="DATA_PATH")
    chroma_path: Path = Field(default=Path("./storage/chroma"), alias="CHROMA_PATH")
    cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")
    collection_name: str = Field(default="advogado_de_bolso", alias="COLLECTION_NAME")

    retrieval_top_k: int = Field(default=5, ge=1, le=50, alias="RETRIEVAL_TOP_K")
    hf_home: Path = Field(default=Path("./storage/hf_cache"), alias="HF_HOME")
    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, ge=1, le=65535, alias="API_PORT")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def resolved_google_api_key(self) -> str:
        return self.gemini_api_key or self.google_api_key

    @property
    def full_model_name(self) -> str:
        return f"{self.llm_provider}:{self.llm_model}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("thinking_level")
    @classmethod
    def _validate_thinking_level(cls, v: str) -> str:
        if v and v not in VALID_THINKING_LEVELS:
            raise ValueError(
                f"THINKING_LEVEL invalido: '{v}'. "
                f"Use um de: {', '.join(VALID_THINKING_LEVELS)} ou vazio para desabilitar."
            )
        return v

    @property
    def google_thinking_config(self) -> dict[str, str] | None:
        """Configuracao de thinking para o Gemma 4, ou None se desabilitado."""
        if not self.thinking_level:
            return None
        return {"thinking_level": self.thinking_level}

    def build_model_settings(self) -> Any:
        """Constroi as configuracoes de modelo de acordo com o provedor."""
        if self.llm_provider != "google":
            return None
        thinking = self.google_thinking_config
        if not thinking:
            return None
        from pydantic_ai.models.google import GoogleModelSettings

        return GoogleModelSettings(google_thinking_config=thinking)  # type: ignore[typeddict-item]

    def build_reviewer_model_settings(self) -> Any:
        """Configuracoes de modelo usadas SOMENTE pelo revisor.

        Force `thinking_level=MINIMAL` regardless of `self.thinking_level`.
        Higher thinking levels expand the reviewer's surface area for
        "found a reason to block", which produced intermittent false
        positives on otherwise acceptable Art. 49 / Art. 26 responses.
        The reviewer is a yes/no gate; minimal thinking is the correct
        knob for that role.
        """
        if self.llm_provider != "google":
            return None
        from pydantic_ai.models.google import GoogleModelSettings

        return GoogleModelSettings(
            google_thinking_config={"thinking_level": "MINIMAL"}  # type: ignore[typeddict-item]
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
