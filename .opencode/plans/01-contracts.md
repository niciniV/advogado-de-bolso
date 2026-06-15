# 01-contracts.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** `src/advogado_de_bolso/contracts.py` spec — `DeadlineResult`, `DraftedDocument`, `KnowledgeChunk` Pydantic envelopes plus the `TipoPrazo`/`Tom` literal aliases.
**Related files:** [02-schemas.md](./02-schemas.md) (wire types that reference these envelopes), [03-adapter.md](./03-adapter.md) (consumer that dispatches on tool return types), [16-tools-modifications.md](./16-tools-modifications.md) (tool return-type changes that produce these envelopes).

### `src/advogado_de_bolso/contracts.py`
Typed tool return envelopes (Pydantic BaseModel). Successes return these; errors return plain strings.

```python
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
    base_legal: str          # "CDC art. 49"
    item_label: str | None
    vicio_oculto: bool
    nota: str


class DraftedDocument(BaseModel):
    tipo: str                # echoes the tool's `tipo` argument
    tom: Tom                 # echoes the tool's `tom` argument
    destinatario: str        # echoes the tool's `destinatario` argument
    texto: str               # the actual drafted prose (from the sub-LLM)


class KnowledgeChunk(BaseModel):
    fonte: str               # never None; "fonte desconhecida" is the fallback
    texto: str
```

Notes:
- `calculos.py` keeps the existing `str` return for its **error paths** (missing `tipo_item`, invalid date, invalid `tipo_prazo`). Only successful calculations return `DeadlineResult`. This means the adapter uses `isinstance(part.content, DeadlineResult)` and gracefully ignores string returns (which represent the LLM asking the user for clarification).
- `DraftedDocument` keeps the full envelope (per Open Issue #8 = A). The redundant `tipo`/`tom`/`destinatario` echoes keep the adapter self-describing; mild LLM-context noise is accepted.
- `KnowledgeChunk.fonte` must preserve the "fonte desconhecida" fallback from `tools/rag.py:39`.

