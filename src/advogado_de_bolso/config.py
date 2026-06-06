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
    collection_name: str = Field(default="advogado_de_bolso", alias="COLLECTION_NAME")

    retrieval_top_k: int = Field(default=5, alias="RETRIEVAL_TOP_K")
    hf_home: Path = Field(default=Path("./storage/hf_cache"), alias="HF_HOME")

    @property
    def resolved_google_api_key(self) -> str:
        return self.gemini_api_key or self.google_api_key

    @property
    def full_model_name(self) -> str:
        return f"{self.llm_provider}:{self.llm_model}"

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

        return GoogleModelSettings(google_thinking_config=thinking)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
