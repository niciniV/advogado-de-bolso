# 16-tools-modifications.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1153-1160)
**In this file:** "Files to Modify" — `tools/calculos.py`, `tools/redigir.py`, `tools/rag.py` (return-type and prompt changes).
**Related files:** [01-contracts.md](./01-contracts.md) (the typed envelopes these tools now return), [05-agent-and-system-prompt.md](./05-agent-and-system-prompt.md) (the `SYSTEM_PROMPT` describes the new tool return shapes), [22-resolved-decisions.md](./22-resolved-decisions.md) (Decision #1 is the authoritative spec for the `redigir_documento` envelope).

### `src/advogado_de_bolso/tools/calculos.py`
Return `DeadlineResult` for successful calculations; keep returning `str` for error paths (missing `tipo_item`, invalid date, invalid `tipo_prazo`). The system prompt instructs the LLM to relay the error string to the user.

### `src/advogado_de_bolso/tools/redigir.py`
Return `DraftedDocument` with `tom: Tom` literal (imported from existing `Tom = Literal[...]` at `tools/redigir.py:24`). Update the docstring to declare the new return shape. ISSUE-USR-017: **keep the "Responda APENAS com o texto final" instruction** in the sub-agent's user prompt at `redigir.py:101-104`. The Open Decision #1 entry (line 1236) is the authoritative spec, and the Files to Modify section's earlier wording ("remove the 'Responda APENAS com o texto final' instruction") is the line being corrected by this fix. The sub-agent remains a plain string producer; the outer `redigir_documento` function wraps its output into a `DraftedDocument` envelope (filling `tipo`/`tom`/`destinatario` from the function's own arguments). The "APENAS" prompt is a domain-specific safety constraint for the legal-drafting sub-agent — it prevents the sub-agent from emitting JSON envelopes or surrounding commentary that would have to be stripped before being placed in `DraftedDocument.texto`. Removing the prompt would risk the sub-agent emitting JSON which would then have to be re-parsed, doubling the failure surface.

### `src/advogado_de_bolso/tools/rag.py`
Return `list[KnowledgeChunk]`. Preserve the "fonte desconhecida" fallback. ISSUE-USR-017: when the retriever returns nothing, return an **empty list `[]`** (NOT a sentinel `KnowledgeChunk(fonte="sistema", ...)`). The previous "no results" sentinel contradicted the test spec (line 1083) and added downstream complexity (the adapter would have to special-case the sentinel, and the SYSTEM_PROMPT's "cite the fonte" wording was ambiguous about whether to cite "sistema"). The empty list is the simplest, most predictable shape: the adapter's `relevant_chunks` falls through, `relevant_title` is `""`, `relevant_content` is `""`, and the system prompt handles the no-results case via the explicit "no relevant info" message. Update the docstring.

