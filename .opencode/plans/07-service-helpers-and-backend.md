# 07-service-helpers-and-backend.md

**Source plan:** revised-integration-plan.md (split round 19)
**In this file:** `service.py` module-scope helpers (`_collect_tool_returns`, `_truncate_history_to_turns`), the `_to_model_messages` removal note (ISSUE-IND-003), `AgentChatBackend` (refactored without reviewer per ISSUE-M3-003), and `build_chat_service` wiring notes.
**Related files:** [06-service-class.md](./06-service-class.md) (`ChatService` class that uses these helpers), [02-schemas.md](./02-schemas.md) (`StructuredChatResponse` built in the backend), [17-config-and-docs-modifications.md](./17-config-and-docs-modifications.md) (the `Settings.cases_path` value is injected via `build_chat_service`).

```python
def _collect_tool_returns(new_messages: list[ModelMessage]) -> list[ToolReturnPart]:
    """Walk the current turn's `new_messages` and collect every `ToolReturnPart`.

    ISSUE-M3-002: this helper is non-trivial; spec'd here so the
    implementer doesn't have to invent it. We scan both `ModelRequest` and
    `ModelResponse` parts (the tool return is a request-side part for the
    next turn, but defensively scan both). ISSUE-USR-002: this MUST be
    called with `result.new_messages()` (current turn only) — never with
    `result.all_messages()`, which would include prior turns' tool returns
    and cause stale `deadline`/`template_letter`/`relevant_chunks` to leak
    into the adapter.
    """
    out: list[ToolReturnPart] = []
    for msg in new_messages:
        for part in msg.parts:
            if isinstance(part, ToolReturnPart):
                out.append(part)
    return out


def _truncate_history_to_turns(
    history: list[ModelMessage], max_turns: int
) -> list[ModelMessage]:
    """Slice `history` to the last `max_turns` user-turn groups.

    ISSUE-USR-003: a single turn that triggers a tool call emits 2-4
    `ModelMessage` objects (one `ModelRequest(parts=[UserPromptPart, ...])`,
    one `ModelResponse(parts=[TextPart, ToolCallPart])`, one or more
    `ModelRequest(parts=[ToolReturnPart])`). Slicing by raw message count
    can cut off a `ToolCallPart` while preserving its matching
    `ToolReturnPart`, producing an invalid provider history. Instead, we
    group messages into turns: a new turn begins at every
    `ModelRequest(parts=[UserPromptPart, ...])` (the user spoke), and any
    messages between user prompts belong to the prior turn. We keep only
    the last `max_turns` turn groups, so every tool call/return pair stays
    paired and we never feed the LLM an orphan `ToolReturnPart`.

    `max_turns < 1` returns an empty list (caller has already validated).
    """
    if max_turns < 1:
        return []
    if not history:
        return []

    # Walk backwards and count user-prompt turn boundaries. A turn group
    # starts at a ModelRequest whose first part is a UserPromptPart, OR
    # at a ModelRequest that contains a UserPromptPart (defensive). The
    # simplest correct heuristic: a turn boundary is any ModelRequest that
    # contains a UserPromptPart.
    turns: list[list[ModelMessage]] = []
    current_turn: list[ModelMessage] = []
    for msg in history:
        is_user_turn_start = (
            isinstance(msg, ModelRequest)
            and any(isinstance(p, UserPromptPart) for p in msg.parts)
        )
        if is_user_turn_start:
            if current_turn:
                turns.append(current_turn)
            current_turn = [msg]
        else:
            current_turn.append(msg)
    if current_turn:
        turns.append(current_turn)

    kept = turns[-max_turns:]
    out: list[ModelMessage] = []
    for t in kept:
        out.extend(t)
    return out


# ISSUE-IND-003: `_to_model_messages(chat_history) -> list[ModelMessage]`
# (previously spec'd here as a fallback when `model_history` was empty) is
# removed. `model_history` is ALWAYS populated on `Case` — initialized to
# `[]` on first creation (line 582) and appended on every subsequent turn
# (line 674). Empty list is a valid input to `_truncate_history_to_turns`
# (returns `[]`), so the helper was effectively unreachable. Defining it
# here as a "fallback" was misleading: no code path in the plan ever
# branched to it. The wire `ChatMessage` carries no `ToolCallPart`/
# `ToolReturnPart` payload, so any wire→model reconstruction would be
# lossy by design — better to surface "no LLM history yet" as the empty
# list it actually is. A future legacy-migration helper (if ever needed)
# would live in `storage/cases.py` alongside the migration shim, not here.
```

The `_backend` protocol stays as a simple `run(message, history) -> (prose, history)` (ISSUE-M3-003). The reviewer is called by `ChatService` exactly once per turn; the backend does not run it.

`AgentChatBackend` (refactored, no reviewer):
```python
class AgentChatBackend:
    """Implements `ChatBackend`. Does NOT run the reviewer — the service does."""

    def __init__(
        self,
        agent: Agent[Deps, str],
        deps_factory: Callable[[], Deps],
    ) -> None:
        self._agent = agent
        self._deps_factory = deps_factory

    async def run(
        self, message: str, history: list[ModelMessage]
    ) -> tuple[str, list[ModelMessage]]:
        deps = self._deps_factory()
        result: AgentRunResult[str] = await self._agent.run(
            message, deps=deps, message_history=history
        )
        prose = result.output  # the final assistant text
        # ISSUE-USR-002: return ONLY the current turn's new messages, not
        # the full `all_messages()` history. `all_messages()` includes the
        # input `message_history` and prior runs, which would cause prior
        # tool returns to leak into the adapter on this turn.
        new_messages = result.new_messages()
        return prose, new_messages
```

ISSUE-REVIEW-008: the service example above is the lint/type-checking contract, not illustrative pseudocode. Keep only imports used by the final implementation, type every function parameter under strict mypy, and parameterize `AgentRunResult[str]`. The service/API batch gate MUST run both `uv run ruff check src/ tests/` and `uv run mypy src/` before proceeding, rather than deferring these failures to the final gate.

`build_chat_service(settings, deps_factory)` wires everything: `AgentChatBackend` + `ReviewerLike` (built from `tools.revisor.review_response`) + `ChatService`. **The `ChatService` constructor receives `cases_path=settings.cases_path`** (ISSUE-USR-007) so the `CASES_PATH` env var actually controls persistence. Without this injection, the env var would be silently ignored (the previous spec hardcoded `Path("./storage/cases")` inside `ChatService.__init__`).

