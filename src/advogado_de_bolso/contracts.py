"""Typed tool return envelopes (Pydantic BaseModel).

Successes return these envelopes; errors return plain strings. The LLM-bound
adapter (added in batch 2) dispatches on `isinstance(part.content, X)` and
gracefully ignores string returns (which represent the LLM asking the user
for clarification, e.g. "informe o tipo de item").
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

TipoPrazo = Literal["reclamacao_vicio", "arrependimento"]
Tom = Literal["formal", "cordial", "firme"]


class DeadlineResult(BaseModel):
    tipo_prazo: TipoPrazo
    data_inicio: date
    data_limite: date
    dias: int
    base_legal: str
    item_label: str | None
    vicio_oculto: bool
    nota: str


class DraftedDocument(BaseModel):
    tipo: str
    tom: Tom
    destinatario: str
    texto: str


class KnowledgeChunk(BaseModel):
    fonte: str
    texto: str
