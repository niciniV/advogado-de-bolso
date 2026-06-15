# 24-out-of-scope.md

**Source plan:** revised-integration-plan.md (split round 19, lines 1405-1416)
**In this file:** Out-of-Scope Notes — multi-worker uvicorn, `_index.json`, auth, API streaming, cross-process writes, lock-registry lifetime, single-task ContextVar scoping, sub-agent LRU cache.
**Related files:** [00-overview-and-architecture.md](./00-overview-and-architecture.md) (the architectural assumptions the out-of-scope notes document), [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) (the `README.md` updates that surface the multi-worker / `<1000`-case / concurrent-write constraints to users), [04-storage.md](./04-storage.md) (the `<1000`-case scalability constraint and the `_index.json` deferral).

## Out-of-Scope Notes

- **Multi-worker `uvicorn`**: not supported. The plan assumes a single worker. Multi-worker would break the in-process `asyncio.Lock` registry and the `_current_style` ContextVar. Document in README.
- **`_index.json`**: not built. `list_all()` scans the directory. Acceptable for the expected scale (<1000 cases, per ISSUE-DS-007 — the constraint is documented in the `storage/cases.py` module docstring and in the project README; a soft `INFO` log fires when the file count exceeds 500). If the scale grows, add a startup disk-scan-rebuild index (not planned now).
- **Auth / multi-user**: not in scope. The plan assumes a single local user.
- **Streaming for the API**: not in scope. The plan's `POST /api/chat/structured` is request/response. The CLI still uses `agent.run_stream` internally, but buffers answer tokens until reviewer approval.
- **Concurrent API + CLI edits to the same case**: not supported. Unique-temp `os.replace` prevents malformed/torn JSON but does not serialize cross-process read-modify-write transactions; simultaneous edits use last-writer-wins semantics.
- **Per-case lock registry lifetime**: locks are intentionally retained until process exit. Under the documented `<1000`-case local-user constraint, this avoids a correctness race at negligible memory cost. If the scale grows, replace the registry with reference-counted lock entries that cannot be evicted while held or awaited.
- **Single-task ContextVar scoping** (ISSUE-DS-008): `_current_style` is a `ContextVar` reset by `chat_structured`'s `try/finally`. It propagates task-locally to any sub-agent run in the same `await` chain. Today no sub-agent reads `_current_style`, so the coupling is safe. If a future sub-agent needs style awareness, it MUST receive the style via `ctx.deps`, not via the ContextVar. The `tests/test_agent.py` extension includes a scoping test that runs a fake sub-agent and asserts the parent ContextVar does not leak after `chat_structured` returns.
- **Sub-agent LRU cache**: the drafting and reviewer sub-agents are cached at module scope (existing pattern at `tools/redigir.py:60`). They are created once and never read `_current_style`. This is the primary mitigation for ISSUE-DS-008.

