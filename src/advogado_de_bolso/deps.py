"""Dependencias injetadas em cada execucao do agente."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from advogado_de_bolso.config import Settings


@dataclass
class Deps:
    """Contexto compartilhado com as tools do agente."""

    settings: Settings
    retriever: Any

    @property
    def model_settings(self) -> Any:
        return self.settings.build_model_settings()
