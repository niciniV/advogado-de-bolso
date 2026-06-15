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
- Drafting and review tools delegate to sub-agents with specialized system prompts
- Sub-agents are cached via `@lru_cache` for reuse
- `RevisionResult` enforces consistency: approved responses cannot have issues

## File Map

| File | Key Exports | Role |
|------|-------------|------|
| `rag.py` | `search_knowledge_base(ctx, query, top_k)` | Retrieves relevant chunks from ChromaDB via `ctx.deps.retriever.aretrieve()`. Returns formatted text with source names. |
| `calculos.py` | `calcular_prazo_consumidor(tipo_prazo, data_inicio_prazo, tipo_item?, vicio_oculto?)` | Pure function (no deps). Computes CDC deadlines: `reclamacao_vicio` (30/90 days) or `arrependimento` (7 days). |
| `redigir.py` | `redigir_documento(ctx, tipo, contexto, objetivo, destinatario, tom)` | Delegates to cached sub-agent with type-specific system prompt. Types: `email_cobranca`, `reclamacao_procon`, `mensagem_rede_social`, `notificacao_extrajudicial`, `recurso`. |
| `revisor.py` | `review_response(question, response, model, model_settings)`, `revisar_resposta(ctx, resposta_original, pergunta_usuario)`, `RevisionResult`, `RevisionRequest` | Independent reviewer agent. Checks legal errors, tone, disclaimers. `RevisionResult.approved_as_is` gates delivery. |

## Work Guidance

### RAG Search (`rag.py`)
- `search_knowledge_base(query, top_k)` retrieves relevant chunks
- Returns formatted text with source attribution
- Respects `RETRIEVAL_TOP_K` config, capped by caller's `top_k`

### Deadline Calculations (`calculos.py`)
- `calcular_prazo_consumidor(tipo_prazo, data_inicio, ...)` computes CDC deadlines
- `reclamacao_vicio` (art. 26): 30 days (non-durable) or 90 days (durable)
- `arrependimento` (art. 49): 7 days from receipt
- Always warns about correct start date dependency

### Document Drafting (`redigir.py`)
- `redigir_documento(tipo, contexto, objetivo, destinatario, tom)` drafts documents
- Types: `email_cobranca`, `reclamacao_procon`, `mensagem_rede_social`, `notificacao_extrajudicial`, `recurso`
- Tones: `formal`, `cordial`, `firme`
- Sub-agent returns only final text, no commentary

### Response Review (`revisor.py`)
- `review_response()` runs independent reviewer on generated responses
- Checks: legal errors, unrealistic expectations, missing sources, tone, disclaimers
- `RevisionResult` has `approved_as_is` flag - blocks delivery if false
- Main agent calls `revisar_resposta()` as tool; service calls `review_response()` directly

## Verification

- Unit tests for each tool in `tests/test_*.py`
- Deadline calculations verified against CDC article text
- Reviewer consistency validator prevents contradictory results
