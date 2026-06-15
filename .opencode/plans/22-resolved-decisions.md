# 22-resolved-decisions.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1332-1344)
**In this file:** "Resolved Open Decisions" — Decision #1 (`redigir_documento` JSON envelope, kept APENAS prompt) and Decision #2 (PATCH only, `UpdateCaseRequest`).
**Related files:** [16-tools-modifications.md](./16-tools-modifications.md) (the `redigir.py` modification that implements Decision #1), [08-api.md](./08-api.md) (the PATCH endpoint that implements Decision #2), [23-issue-tracking-table.md](./23-issue-tracking-table.md) (Decision #3 is the granular ISSUE-* / REVIEW-* / USR-* fix table).

## Resolved Open Decisions

### 1. `redigir_documento` JSON envelope in LLM context — **RESOLVED**
- **Tool docstring** updated to declare `DraftedDocument` return shape with `texto` as the body.
- **Sub-agent user prompt** at `redigir.py:101-104` is **kept** ("Responda APENAS com o texto final"). The sub-agent is a **plain string producer**; the outer `redigir_documento` function wraps its output into a `DraftedDocument` envelope (filling `tipo`/`tom`/`destinatario` from the function's own arguments). The sub-LLM does NOT need to produce JSON; only the outer Python wrapper does.
- **Main agent system prompt** at `agent.py` updated: "When `redigir_documento` returns, it gives you a JSON object with `tipo`, `tom`, `destinatario`, and `texto`. Present only the `texto` field to the user as the document body. Do not paraphrase or summarize it."
- **Contract test** in `test_adapter.py`: a redigir turn produces `structured.template_letter == doc.texto`.

### 2. `PUT` vs `PATCH` for rename — **RESOLVED: PATCH only**
- One endpoint: `PATCH /api/cases/{case_id}` with `UpdateCaseRequest { title?, icon_name?, response_style? }` (a single-field rename is just `UpdateCaseRequest { title }`).
- REST-correct (partial update).
- The Open Decision "PUT for full replacement" is deferred until there's a UI consumer for it.
- Originally specified as `RenameCaseRequest { title }`; expanded to `UpdateCaseRequest` per ISSUE-USR-005 to also carry `icon_name` and `response_style` in the same PATCH.

