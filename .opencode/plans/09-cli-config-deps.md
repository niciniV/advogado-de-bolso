# 09-cli-config-deps.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** `src/advogado_de_bolso/cli.py` spec (reviewer-gated buffered streaming), `config.py` addition (`cases_path` env alias), and the `deps.py` "no changes" note.
**Related files:** [06-service-class.md](./06-service-class.md) (the `REVIEW_BLOCKED_MESSAGE` constant and reviewer-call convention that the CLI also uses), [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) (config.py and .env.example modification specs that mirror the additions here), [15-backend-tests.md](./15-backend-tests.md) (`test_cli.py` pins the reviewer-gated buffering behavior).

### `src/advogado_de_bolso/cli.py`
Stays on `agent.run_stream` (per Open Issue #1 = A), but generation is buffered behind the mandatory reviewer gate. Writes approved case files via the storage layer directly.

- Build the agent once via `build_agent(settings)`.
- Build a `KnowledgeIndex` and `Deps` as today.
- Use a per-CLI-session `model_history: list[ModelMessage]` (in-memory).
- Accumulate streamed tokens internally while the Live UI shows only a spinner/status. After generation completes, call `review_response(question=user_input, response=accumulated, ...)`.
- If review blocks, display only `REVIEW_BLOCKED_MESSAGE`; do not display the generated prose, append its `new_messages`, or save the turn.
- If review approves, render the complete answer, append the approved turn's `result.new_messages()` to `model_history` plus the UI messages to `chat_history`, and save the case file to `./storage/cases/{session_id}.json`.
- The CLI constructs a `Case` object with both `chat_history` and `model_history` populated, then calls `cases.save(case, cases_path=settings.cases_path)` (ISSUE-DS-010 + ISSUE-USR-007). Saving only `chat_history` would leave `model_history == []` on disk, and a subsequent API turn on the same case would lose tool-call/return context (per ISSUE-M3-001). The persistence path is shared with the API, so the saved shape must match. The CLI reads `settings.cases_path` (env `CASES_PATH`) so the env var works for both transports.
- Spinner/live-status UX is preserved; token-by-token answer display is removed because it would expose content before mandatory review.
- **CLI/API concurrent write limitation**: the storage layer uses a unique same-directory temp file plus `os.replace`, preventing torn JSON and temp-file collisions. It does not serialize cross-process read-modify-write transactions. Concurrent API and CLI edits to the same case are unsupported and last-writer-wins; document this in README and the Out-of-Scope Notes.

### `src/advogado_de_bolso/config.py`
Add `cases_path: Path = Field(default=Path("./storage/cases"), alias="CASES_PATH")` (ISSUE-M3-014). The env alias keeps `Settings` consistent with `DATA_PATH` / `CHROMA_PATH` / `HF_HOME` which all use `Field(..., alias=...)`.

### `src/advogado_de_bolso/deps.py`
**No changes.** Per Open Issue #5 and #11: `response_style` does NOT live on `Deps`. The `@agent.instructions` callback reads from `_current_style` (a `ContextVar`). The ContextVar is task-local and is reset by `chat_structured`'s `try/finally` (ISSUE-DS-008). Sub-agents in this codebase (`redigir_documento`, `revisar_resposta`) do NOT read `_current_style` and are safe. If a future sub-agent needs style awareness, it must be passed explicitly via `ctx.deps`, not via the ContextVar.

