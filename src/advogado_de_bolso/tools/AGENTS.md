# tools - Agent Tools

## Purpose

Specialized tools invoked by the main agent to perform domain-specific tasks: knowledge base search, CDC deadline calculations, document drafting, and response quality review.

## Ownership

- `rag.py` - RAG search against the knowledge base
- `calculos.py` - CDC deadline calculations (art. 26, art. 49)
- `redigir.py` - Document drafting via sub-agents
- `revisor.py` - Response review and quality gate

## Local Contracts

- All tool outputs MUST be in Brazilian Portuguese
- Tools receive `RunContext[Deps]` and access settings/retriever via `ctx.deps`
- **Tool return shapes are typed envelopes** from `advogado_de_bolso.contracts`:
  - `calcular_prazo_consumidor` → `DeadlineResult` on success, plain `str` on error path (missing `tipo_item`, invalid date, invalid `tipo_prazo`).
  - `redigir_documento` → `DraftedDocument` (tipo, tom, destinatario, texto).
  - `search_knowledge_base` → `list[KnowledgeChunk]` (empty `[]` when the retriever has no hits — NOT a sentinel chunk).
- Drafting and review tools delegate to sub-agents with specialized system prompts
- Sub-agents are cached via `@lru_cache` for reuse
- The `Tom` alias is the canonical `contracts.Tom`; `tools/redigir.py` re-exports it for backward-compat (`from .redigir import Tom` keeps working)
- `RevisionResult` enforces consistency: approved responses cannot have issues

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `rag.py` | `search_knowledge_base(ctx, query, top_k) -> list[KnowledgeChunk]` | Retrieves relevant chunks from ChromaDB via `ctx.deps.retriever.aretrieve()`. Returns `[]` (empty list) when there are no hits, never a sentinel chunk. |
| `calculos.py` | `calcular_prazo_consumidor(tipo_prazo, data_inicio_prazo, tipo_item?, vicio_oculto?) -> DeadlineResult \| str` | Pure function (no deps). Computes CDC deadlines: `reclamacao_vicio` (30/90 days) or `arrependimento` (7 days). Success path returns a `DeadlineResult`; error paths (invalid date, missing `tipo_item`, invalid `tipo_prazo`) return `str` for the LLM to relay. |
| `redigir.py` | `redigir_documento(ctx, tipo, contexto, objetivo, destinatario, tom) -> DraftedDocument`, `TipoDocumento`, `Tom` | Delegates to cached sub-agent with type-specific system prompt. Wraps the sub-agent's plain-string output into a `DraftedDocument` envelope (filling `tipo`/`tom`/`destinatario` from the function's own arguments). The "Responda APENAS com o texto final" instruction is kept in the sub-agent's user prompt (ISSUE-USR-017). `Tom` is imported and re-exported from `advogado_de_bolso.contracts`. |
| `revisor.py` | `review_response(question, response, model, model_settings)`, `revisar_resposta(ctx, resposta_original, pergunta_usuario)`, `RevisionResult`, `RevisionRequest` | Independent reviewer agent. Checks legal errors, tone, disclaimers. `RevisionResult.approved_as_is` gates delivery. |

## Work Guidance

### RAG Search (`rag.py`)
- `search_knowledge_base(query, top_k)` retrieves relevant chunks
- Returns `list[KnowledgeChunk]` ordered by score descending
- `fonte` falls back to `node_id` then to the literal string `"fonte desconhecida"` (always non-None)
- Empty result is `[]`, never a sentinel chunk
- Respects `RETRIEVAL_TOP_K` config, capped by caller's `top_k`

### Deadline Calculations (`calculos.py`)
- `calcular_prazo_consumidor(tipo_prazo, data_inicio, ...)` computes CDC deadlines
- `reclamacao_vicio` (art. 26): 30 days (non-durable) or 90 days (durable)
- `arrependimento` (art. 49): 7 days from receipt
- Success → `DeadlineResult`; error → `str` (caller relays to the user)
- `DeadlineResult.nota` warns about the correct start date (`vicio_oculto=True` → "data em que o vicio oculto ficou evidente ao consumidor"; otherwise → "data de entrega do produto ou de conclusao do servico"; `arrependimento` → "data de recebimento do produto ou da contratacao do servico")

### Document Drafting (`redigir.py`)
- `redigir_documento(tipo, contexto, objetivo, destinatario, tom)` drafts documents and returns a `DraftedDocument`
- Types: `email_cobranca`, `reclamacao_procon`, `mensagem_rede_social`, `notificacao_extrajudicial`, `recurso`
- Tones: `formal`, `cordial`, `firme` (from `contracts.Tom`)
- Sub-agent returns only final text (the "Responda APENAS com o texto final" prompt is preserved); the outer function wraps it in a `DraftedDocument`

### Response Review (`revisor.py`)
- `review_response()` runs independent reviewer on generated responses
- Checks: legal errors, unrealistic expectations, missing sources, tone, disclaimers
- `RevisionResult` has `approved_as_is` flag - blocks delivery if false
- Main agent calls `revisar_resposta()` as tool; service calls `review_response()` directly

## Verification

- Unit tests for each tool in `tests/test_*.py`
- Deadline calculations verified against CDC article text
- Reviewer consistency validator prevents contradictory results
