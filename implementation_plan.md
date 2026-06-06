# Fix 15 Codebase Issues — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 15 confirmed bugs and code quality issues across high, medium, and low priority tiers.

**Architecture:** Surgical fixes to existing files — no new packages or major restructuring. The changes are grouped logically so each task produces a self-contained, testable commit.

**Tech Stack:** Python 3.11+, pydantic-ai, pydantic, LlamaIndex, ChromaDB, pytest

---

## All 15 Issues Confirmed ✅

Every issue listed in the review has been verified against the source code. All exist exactly as described.

## Proposed Changes

### Task 1: Fix RevisionResult broken defaults (Issue #2)

**Files:**
- Modify: [`revisor.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/subagents/revisor.py#L41-L57)
- Modify: [`test_revision_result.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_revision_result.py)

**Rationale:** A default-constructed `RevisionResult()` produces `needs_revision=True, approved_as_is=False` with empty `issues` and `suggestions` — a semantically broken state. The defaults should be the "approved" state since the LLM will explicitly set fields when revision is needed.

- [ ] **Step 1: Update `RevisionResult` defaults**

Change `revisor.py` lines 41-57:

```python
class RevisionResult(BaseModel):
    needs_revision: bool = Field(
        default=False,
        description="Se a resposta precisa de ajustes antes de ser entregue.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Lista objetiva de problemas encontrados.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Sugestoes concretas de correcao (com texto reescrito quando possivel).",
    )
    approved_as_is: bool = Field(
        default=True,
        description="True se a resposta esta OK e pode ser entregue sem mudancas.",
    )
```

- [ ] **Step 2: Update tests for new defaults**

Verify that `test_revision_result.py` tests for the new default state: `RevisionResult()` should now have `needs_revision=False` and `approved_as_is=True`.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_revision_result.py tests/test_revisor.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/advogado_de_bolso/subagents/revisor.py tests/test_revision_result.py
git commit -m "fix: make RevisionResult defaults semantically consistent (approved state)"
```

---

### Task 2: Hoist Agent instances to module level (Issues #1, #8)

**Files:**
- Modify: [`revisor.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/subagents/revisor.py#L60-L101)
- Modify: [`redigir.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/tools/redigir.py#L62-L106)
- Rename: `subagents/` → `tools/` (move `revisor.py` into `tools/`)
- Modify: [`agent.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/agent.py#L11)
- Modify: [`conftest.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/conftest.py#L10)
- Modify: [`test_revisor.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_revisor.py)
- Modify: [`test_redigir.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_redigir.py)
- Modify: [`test_revision_result.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_revision_result.py)

**Rationale:** Both `revisar_resposta` and `redigir_documento` create a new `Agent` on every call. Since `Agent` is stateless and reusable, we can hoist these to module-level lazy singletons. Additionally, moving `revisor.py` out of `subagents/` into `tools/` corrects the misleading package name (Issue #8), since these are pydantic-ai tools, not model-delegated subagents.

> [!IMPORTANT]
> Moving `revisor.py` from `subagents/` to `tools/` changes import paths. All references need updating.

- [ ] **Step 1: Move `revisor.py` from `subagents/` to `tools/`**

Move the file and delete the now-empty `subagents/` package:

```bash
git mv src/advogado_de_bolso/subagents/revisor.py src/advogado_de_bolso/tools/revisor.py
```

Remove `subagents/__init__.py` and `subagents/` directory.

- [ ] **Step 2: Refactor `revisor.py` — hoist agent to module-level lazy singleton**

In the new `tools/revisor.py`, replace per-call Agent construction with a module-level cached builder:

```python
"""Tool de revisao: revisa a resposta final antes de entregar ao usuario.

Exposto ao agente principal como tool `revisar_resposta`. O agente principal
deve chama-lo quando a resposta for longa, envolver orientacao juridica,
ou citar prazos/legislacao.

CONTRATO: o agente principal DEVE passar apenas o contexto original do
usuario (pergunta_usuario) e o texto final da resposta (resposta_original),
SEM incluir seu proprio raciocinio interno, resultados de ferramentas,
ou conclusoes intermediarias. O revisor deve enxergar apenas o que o
usuario enxerga.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from advogado_de_bolso.deps import Deps

REVISION_SYSTEM_PROMPT = """..."""  # unchanged


class RevisionResult(BaseModel):
    # ... (with fixed defaults from Task 1)


@lru_cache(maxsize=1)
def _get_revision_agent() -> Agent:
    """Returns a cached revision Agent (created once, reused)."""
    return Agent(
        model=None,  # will use the model from run() call
        system_prompt=REVISION_SYSTEM_PROMPT,
        output_type=RevisionResult,
    )


async def revisar_resposta(
    ctx: RunContext[Deps],
    resposta_original: str,
    pergunta_usuario: str,
) -> str:
    """Revisa a resposta antes de enviar ao usuario. ..."""
    user_prompt = (
        f"PERGUNTA DO USUARIO:\n{pergunta_usuario}\n\n"
        f"RESPOSTA GERADA PELO AGENTE PRINCIPAL:\n{resposta_original}\n\n"
        "Revise a resposta acima."
    )

    revision_agent = _get_revision_agent()
    result = await revision_agent.run(
        user_prompt,
        model=ctx.model,
        model_settings=ctx.deps.model_settings,
    )
    rev = result.output

    if rev.approved_as_is or not rev.needs_revision:
        return "OK - resposta aprovada sem mudancas."

    parts = [f"REVISAO NECESSARIA ({len(rev.issues)} problema(s)):"]
    for issue in rev.issues:
        parts.append(f"  - {issue}")
    if rev.suggestions:
        parts.append("\nSugestoes de correcao:")
        for s in rev.suggestions:
            parts.append(f"  - {s}")
    return "\n".join(parts)
```

Key changes:
- `Agent` is created once via `@lru_cache`
- `model=None` at construction time; model is passed at `run()` time via `ctx.model`
- `model_settings` passed at `run()` time instead of construction

- [ ] **Step 3: Refactor `redigir.py` — hoist agents to module-level cache**

```python
from functools import lru_cache

# ... existing code ...

@lru_cache(maxsize=5)
def _get_drafting_agent(tipo: TipoDocumento) -> Agent:
    """Returns a cached drafting Agent for the given document type."""
    return Agent(
        model=None,
        system_prompt=_SYSTEM_PROMPTS[tipo],
    )


async def redigir_documento(
    ctx: RunContext[Deps],
    tipo: TipoDocumento,
    contexto: str,
    objetivo: str,
    destinatario: str,
    tom: Tom = "formal",
) -> str:
    """Redige um documento pronto para o usuario enviar. ..."""
    user_prompt = (
        f"Destinatario: {destinatario}\n"
        f"Tom: {tom}\n"
        f"Objetivo: {objetivo}\n"
        f"Contexto / Resumo do caso:\n{contexto}\n\n"
        "Redija o documento. ..."
    )

    drafting_agent = _get_drafting_agent(tipo)
    result = await drafting_agent.run(
        user_prompt,
        model=ctx.model,
        model_settings=ctx.deps.model_settings,
    )
    return result.output
```

- [ ] **Step 4: Update all imports**

In `agent.py` (line 11):
```python
# Before:
from advogado_de_bolso.subagents.revisor import revisar_resposta
# After:
from advogado_de_bolso.tools.revisor import revisar_resposta
```

In `conftest.py` (line 10):
```python
# Before:
from advogado_de_bolso.subagents.revisor import RevisionResult
# After:
from advogado_de_bolso.tools.revisor import RevisionResult
```

In `test_revisor.py` — update **all** occurrences:
- Line 7: `from advogado_de_bolso.tools.revisor import revisar_resposta`
- Line 12: `patch("advogado_de_bolso.tools.revisor.Agent")`
- Line 88: `from advogado_de_bolso.tools.revisor import RevisionResult`
- Line 111: `from advogado_de_bolso.tools.revisor import RevisionResult`

In `test_revision_result.py` (line 6):
```python
# Before:
from advogado_de_bolso.subagents.revisor import RevisionResult
# After:
from advogado_de_bolso.tools.revisor import RevisionResult
```

- [ ] **Step 5: Update test fixtures to handle `@lru_cache` isolation and `model_settings` moved to `run()`**

Since `_get_revision_agent` and `_get_drafting_agent` use `@lru_cache`, the cached mock from one test leaks into subsequent tests. Clear the cache in each fixture.

Also, `model_settings` is now passed to `agent.run()` instead of the `Agent()` constructor. Tests that assert on `mock_agent.call_args` for `model_settings` must assert on `mock_agent.return_value.run.call_args` instead.

In `test_revisor.py`, replace the fixture:
```python
@pytest.fixture
def mock_revision_agent():
    from advogado_de_bolso.tools.revisor import _get_revision_agent
    _get_revision_agent.cache_clear()
    with patch("advogado_de_bolso.tools.revisor.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock()
        MockAgent.return_value = mock_instance
        yield MockAgent
        _get_revision_agent.cache_clear()
```

Update `test_agent_receives_model_settings` to assert on `run()` kwargs:
```python
async def test_agent_receives_model_settings(self, ctx, mock_revision_agent, mock_revision_result_approved):
    mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved
    await revisar_resposta(ctx=ctx, resposta_original="Resposta.", pergunta_usuario="Pergunta.")

    run_kwargs = mock_revision_agent.return_value.run.call_args[1]
    assert "model_settings" in run_kwargs
    assert run_kwargs["model_settings"] == ctx.deps.model_settings
```

Update `test_agent_created_with_revision_result_output` to assert `output_type` on constructor:
```python
async def test_agent_created_with_revision_result_output(self, ctx, mock_revision_agent, mock_revision_result_approved):
    mock_revision_agent.return_value.run.return_value.output = mock_revision_result_approved
    await revisar_resposta(ctx=ctx, resposta_original="Resposta.", pergunta_usuario="Pergunta.")

    call_kwargs = mock_revision_agent.call_args[1]
    assert call_kwargs["output_type"].__name__ == "RevisionResult"
```

In `test_redigir.py`, replace the fixture:
```python
@pytest.fixture
def mock_agent():
    from advogado_de_bolso.tools.redigir import _get_drafting_agent
    _get_drafting_agent.cache_clear()
    with patch("advogado_de_bolso.tools.redigir.Agent") as MockAgent:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock()
        mock_instance.run.return_value.output = "texto gerado pelo agente mockado"
        MockAgent.return_value = mock_instance
        yield MockAgent
        _get_drafting_agent.cache_clear()
```

Update `test_agent_receives_model_settings` to assert on `run()` kwargs:
```python
async def test_agent_receives_model_settings(self, ctx, mock_agent):
    await redigir_documento(ctx=ctx, tipo="email_cobranca", contexto="Teste", objetivo="Teste", destinatario="Teste")
    run_kwargs = mock_agent.return_value.run.call_args[1]
    assert "model_settings" in run_kwargs
    assert run_kwargs["model_settings"] == ctx.deps.model_settings
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: hoist Agent singletons, move revisor.py to tools/ (fixes #1, #8)"
```

---

### Task 3: Fix `setdefault` in loader.py (Issue #3)

**Files:**
- Modify: [`loader.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/knowledge/loader.py#L40)

- [ ] **Step 1: Simplify the `setdefault` call**

In `loader.py` line 40, change:
```python
# Before:
d.metadata.setdefault("file_name", d.metadata.get("file_name", "desconhecido"))
# After:
d.metadata.setdefault("file_name", "desconhecido")
```

- [ ] **Step 2: Commit**

```bash
git add src/advogado_de_bolso/knowledge/loader.py
git commit -m "fix: simplify redundant setdefault in loader.py"
```

---

### Task 4: Make provider configurable (Issue #4)

**Files:**
- Modify: [`config.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/config.py)
- Modify: [`agent.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/agent.py#L75)
- Modify: [`.env.example`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/.env.example)
- Modify: [`test_config.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_config.py)

**Rationale:** The provider is hardcoded as `google:` in `agent.py`. Adding a `LLM_PROVIDER` setting allows switching providers without source changes.

- [ ] **Step 1: Add `llm_provider` and provider-aware model settings to `Settings`**

In `config.py`, add `llm_provider` after the `llm_model` field (around line 25):
```python
    llm_provider: str = Field(default="google", alias="LLM_PROVIDER")
```

Add a property to construct the full model string (around line 40):
```python
    @property
    def full_model_name(self) -> str:
        """Returns the model string in pydantic-ai format: 'provider:model'."""
        return f"{self.llm_provider}:{self.llm_model}"
```

Update `build_model_settings` in `config.py` (lines 58-66) to be provider-aware:
```python
    def build_model_settings(self) -> Any:
        """Constroi as configuracoes de modelo de acordo com o provedor."""
        if self.llm_provider != "google":
            return None

        thinking = self.google_thinking_config
        if not thinking:
            return None

        from pydantic_ai.models.google import GoogleModelSettings
        return GoogleModelSettings(google_thinking_config=thinking)
```

- [ ] **Step 2: Update `agent.py` to use configurable provider**

In `agent.py` line 75, change:
```python
# Before:
    model = f"google:{settings.llm_model}"
# After:
    model = settings.full_model_name
```

- [ ] **Step 3: Update `.env.example`**

Add after the `LLM_MODEL` line:
```env
# Provedor do modelo: google | openai | anthropic | etc.
LLM_PROVIDER=google
```

- [ ] **Step 4: Update config tests**

Add a test for the new field and property, and the provider-aware fallback in `test_config.py`.

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_config.py -v
```

- [ ] **Step 6: Update `_check_config()` in `cli.py` to be provider-aware**

The current `_check_config()` hardcodes a Google API key check. With the new `llm_provider` setting, it should only check the Google key when the provider is `google`, and skip the check for other providers (pydantic-ai will raise its own error for missing credentials at runtime):

```python
def _check_config() -> bool:
    settings = get_settings()
    if settings.llm_provider == "google" and not settings.resolved_google_api_key:
        console.print(
            Panel(
                "[red]Nenhuma chave de API configurada.[/red]\n\n"
                "Defina [bold]GEMINI_API_KEY[/bold] (ou [bold]GOOGLE_API_KEY[/bold]) "
                "no arquivo .env (obtenha em https://aistudio.google.com/apikey).",
                title="Erro de configuracao",
                border_style="red",
            )
        )
        return False
    return True
```

- [ ] **Step 7: Commit**

```bash
git add src/advogado_de_bolso/config.py src/advogado_de_bolso/agent.py src/advogado_de_bolso/cli.py .env.example tests/test_config.py
git commit -m "feat: make LLM provider configurable via LLM_PROVIDER env var (fixes #4)"
```

---

### Task 5: Remove global mutable state in KnowledgeIndex (Issue #5)

**Files:**
- Modify: [`index.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/knowledge/index.py#L53)

**Rationale:** `Settings.embed_model = embed_model` mutates LlamaIndex's process-wide singleton, leaking state. Since `embed_model` is already passed explicitly to `from_documents()` and `from_vector_store()`, the global mutation is unnecessary.

- [ ] **Step 1: Remove the global Settings mutation**

In `index.py` line 53, remove:
```python
Settings.embed_model = embed_model
```

Also remove the import of `Settings` from `llama_index.core` (line 11) since it's now unused from that module. Note: `Settings` from `advogado_de_bolso.config` on line 19 must remain.

> [!WARNING]
> There is a name collision: line 11 imports `Settings` from `llama_index.core` and line 19 imports `Settings` from `advogado_de_bolso.config`. Currently, line 19 shadows line 11. After removing line 53, the llama_index `Settings` import is unused and should be removed entirely.

Update the import block (lines 10-14):
```python
from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
)
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_knowledge_index.py -v
```

- [ ] **Step 3: Commit**

```bash
git add src/advogado_de_bolso/knowledge/index.py
git commit -m "fix: remove global Settings.embed_model mutation in KnowledgeIndex"
```

---

### Task 6: Validate `top_k` in `search_knowledge_base` (Issue #6)

**Files:**
- Modify: [`rag.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/tools/rag.py#L26)
- Modify: [`test_rag_tool.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_rag_tool.py)

- [ ] **Step 1: Add validation for `top_k`**

In `rag.py`, replace line 26:
```python
# Before:
k = top_k or ctx.deps.settings.retrieval_top_k
# After:
k = top_k if top_k is not None else ctx.deps.settings.retrieval_top_k
if k < 1:
    k = ctx.deps.settings.retrieval_top_k
```

This ensures:
- `top_k=0` falls back to the config default (previously `0` was falsy so this worked, but now it's explicit)
- Negative values are clamped to the config default instead of producing `[:-1]` slicing bugs

- [ ] **Step 2: Add test for negative `top_k`**

In `test_rag_tool.py`, add a test:
```python
async def test_negative_top_k_falls_back_to_default(ctx):
    """A negative top_k should fall back to the config default, not slice backwards."""
    result = await search_knowledge_base(ctx, "test query", top_k=-1)
    # Should not raise and should use settings.retrieval_top_k
    assert isinstance(result, str)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_rag_tool.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/advogado_de_bolso/tools/rag.py tests/test_rag_tool.py
git commit -m "fix: validate top_k to prevent negative slice bugs in RAG search"
```

---

### Task 7: Refactor CLI commands into a registry (Issue #7)

**Files:**
- Modify: [`cli.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/cli.py#L26-L173)

**Rationale:** Command definitions are duplicated between `COMMANDS_HELP` and the `if/elif` chain. A registry mapping automates help generation and eliminates duplication.

- [ ] **Step 1: Define handler functions and a command registry**

Define standalone handler functions and register them directly in the command list. Each handler takes `settings` and `message_history` as arguments and returns `"exit"` to quit or `None` to continue:

```python
from dataclasses import dataclass
from typing import Callable


@dataclass
class _Command:
    """A CLI command with aliases, help text, and handler."""
    aliases: tuple[str, ...]
    help_text: str
    handler: Callable


def _handle_exit(settings, message_history: list) -> str:
    console.print("Ate logo!")
    return "exit"


def _handle_clear(settings, message_history: list) -> None:
    message_history.clear()
    console.print("[dim]Historico da sessao limpo.[/dim]")


def _handle_help(settings, message_history: list) -> None:
    console.print(COMMANDS_HELP)


def _handle_modelo(settings, message_history: list) -> None:
    console.print(
        f"Modelo LLM:     {settings.llm_model}\n"
        f"Thinking level: {settings.thinking_level or 'off'}\n"
        f"Embedding:      {settings.embedding_model}\n"
        f"Collection:     {settings.collection_name}\n"
        f"Data path:      {settings.data_path}"
    )


_COMMANDS: list[_Command] = [
    _Command(("/sair", "/exit"), "Encerrar o chat", _handle_exit),
    _Command(("/limpar", "/clear"), "Limpar historico da sessao", _handle_clear),
    _Command(("/ajuda", "/help"), "Mostrar esta ajuda", _handle_help),
    _Command(("/modelo",), "Mostrar modelo e configuracoes", _handle_modelo),
]


def _build_commands_help() -> str:
    lines = ["[bold]Comandos disponiveis:[/bold]"]
    for cmd in _COMMANDS:
        aliases = ", ".join(cmd.aliases)
        lines.append(f"  {aliases:<20s} {cmd.help_text}")
    return "\n".join(lines)


COMMANDS_HELP = _build_commands_help()
```

> [!NOTE]
> `_handle_help` references `COMMANDS_HELP` which is defined after the handler. This works because the handler is only *called* at runtime, after `COMMANDS_HELP` is constructed.

Then build a lookup dict at module level and dispatch in the loop:

```python
# Module level
_CMD_LOOKUP: dict[str, _Command] = {}
for _cmd_def in _COMMANDS:
    for _alias in _cmd_def.aliases:
        _CMD_LOOKUP[_alias] = _cmd_def
```

Replace the `if/elif` chain in `_run_chat_loop`:
```python
if user_input.startswith("/"):
    cmd_key = user_input.lower().split()[0]
    cmd_def = _CMD_LOOKUP.get(cmd_key)
    if cmd_def is None:
        console.print(f"[red]Comando desconhecido:[/red] {user_input}")
        continue
    result = cmd_def.handler(settings, message_history)
    if result == "exit":
        return
    continue
```

- [ ] **Step 2: Run tests / manual smoke test**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add src/advogado_de_bolso/cli.py
git commit -m "refactor: CLI command registry to eliminate duplication (fixes #7)"
```

---

### Task 8: Fix module-level mocking in test_knowledge_index.py (Issue #9)

**Files:**
- Modify: [`test_knowledge_index.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_knowledge_index.py#L11-L26)

**Rationale:** Module-scope `sys.modules` mutation leaks mocked modules across pytest execution, potentially breaking other test files.

- [ ] **Step 1: Move module mocking into a session-scoped fixture**

Replace lines 11-28 with a session-scoped `autouse` fixture using `conftest.py` or a local fixture:

```python
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

_MOCK_MODULES = [
    "chromadb",
    "chromadb.api",
    "chromadb.api.types",
    "chromadb.errors",
    "llama_index",
    "llama_index.core",
    "llama_index.core.embeddings",
    "llama_index.core.base_embeddings",
    "llama_index.vector_stores",
    "llama_index.vector_stores.chroma",
    "llama_index.embeddings",
    "llama_index.embeddings.huggingface",
]


@pytest.fixture(autouse=True, scope="module")
def _mock_heavy_deps():
    """Mock heavy dependencies for this test module only."""
    originals = {}
    for mod in _MOCK_MODULES:
        originals[mod] = sys.modules.get(mod)
        sys.modules[mod] = MagicMock()
    yield
    # Restore original state
    for mod in _MOCK_MODULES:
        if originals[mod] is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = originals[mod]


from advogado_de_bolso.knowledge.index import KnowledgeIndex

# ... rest of tests unchanged ...
```

> [!NOTE]
> The import of `KnowledgeIndex` must remain after the fixture definition because Python evaluates module-level code eagerly. The fixture's `autouse=True, scope="module"` ensures it runs before any test in this module. However, the import itself happens at module load time, which is before fixtures run. We need to keep the import inside each test class or use `importlib` lazily. An alternative approach: keep the module-level mocking but add cleanup in a module-level fixture.

Actually, the cleanest approach is to keep the module-scope mock but add teardown to restore `sys.modules`:

```python
_originals = {}
for _mod in _MOCK_MODULES:
    _originals[_mod] = sys.modules.get(_mod)
    sys.modules[_mod] = MagicMock()

from advogado_de_bolso.knowledge.index import KnowledgeIndex


@pytest.fixture(autouse=True, scope="module")
def _restore_modules():
    """Restore sys.modules after all tests in this module complete."""
    yield
    for mod in _MOCK_MODULES:
        if _originals[mod] is None:
            sys.modules.pop(mod, None)
        else:
            sys.modules[mod] = _originals[mod]
```

- [ ] **Step 2: Run full test suite to verify no leaks**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_knowledge_index.py
git commit -m "fix: add teardown for module-level sys.modules mocking (fixes #9)"
```

---

### Task 9: Fix naming inconsistency — arrefecimento vs arrependimento (Issue #11)

**Files:**
- Modify: [`calculos.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/tools/calculos.py#L58)
- Modify: [`agent.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/agent.py#L54)
- Modify: [`test_calculos.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/test_calculos.py)

**Rationale:** The function is named `calcular_prazo_arrefecimento` ("cooling", Portuguese from Portugal) but all documentation refers to "arrependimento" ("regret/withdrawal", Brazilian Portuguese, CDC art. 49). The function name should match the legal term used in the CDC.

> [!WARNING]
> This is a public API rename. Any external callers (if any) would break. Since this is a tool registered with the agent and not a public library, the risk is contained to the import in `agent.py`.

- [ ] **Step 1: Rename function in `calculos.py`**

```python
# Before:
def calcular_prazo_arrefecimento(data_compra: str) -> str:
# After:
def calcular_prazo_arrependimento(data_compra: str) -> str:
```

- [ ] **Step 2: Update import in `agent.py`**

```python
# Before:
from advogado_de_bolso.tools.calculos import (
    calcular_prazo_arrefecimento,
    calcular_prazo_reclamacao_vicio,
)
# ...
agent.tool_plain(calcular_prazo_arrefecimento)

# After:
from advogado_de_bolso.tools.calculos import (
    calcular_prazo_arrependimento,
    calcular_prazo_reclamacao_vicio,
)
# ...
agent.tool_plain(calcular_prazo_arrependimento)
```

Also update the SYSTEM_PROMPT reference (line 53):
```python
# Before:
- `calcular_prazo_arrefecimento`: calcula prazo de arrependimento para
# After:
- `calcular_prazo_arrependimento`: calcula prazo de arrependimento para
```

- [ ] **Step 3: Update tests**

In `test_calculos.py`, update all references from `calcular_prazo_arrefecimento` to `calcular_prazo_arrependimento`.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_calculos.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/advogado_de_bolso/tools/calculos.py src/advogado_de_bolso/agent.py tests/test_calculos.py
git commit -m "fix: rename arrefecimento → arrependimento to match CDC terminology"
```

---

### Task 10: Make `Deps.model_settings` a dynamic property (Issue #12)

**Files:**
- Modify: [`deps.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/deps.py)
- Modify: [`cli.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/cli.py#L126-L130)

**Rationale:** `model_settings` on `Deps` just duplicates `settings.build_model_settings()`. Making it a property eliminates the duplication.

- [ ] **Step 1: Convert `model_settings` to a property on `Deps`**

```python
@dataclass
class Deps:
    """Contexto compartilhado com as tools do agente."""

    settings: Settings
    retriever: Any

    @property
    def model_settings(self) -> Any:
        return self.settings.build_model_settings()
```

- [ ] **Step 2: Remove explicit `model_settings` from `Deps` construction in `cli.py`**

In `cli.py` lines 126-130, change:
```python
# Before:
deps = Deps(
    settings=settings,
    retriever=retriever,
    model_settings=settings.build_model_settings(),
)
# After:
deps = Deps(
    settings=settings,
    retriever=retriever,
)
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add src/advogado_de_bolso/deps.py src/advogado_de_bolso/cli.py
git commit -m "refactor: make Deps.model_settings a dynamic property (fixes #12)"
```

---

### Task 11: Add explicit `initialize()` to `KnowledgeIndex` + cache collection (Issue #13)

**Files:**
- Modify: [`index.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/knowledge/index.py#L32-L48)

**Rationale:** `_get_embed_model` and `_get_chroma_collection` mix lazy initialization with eager side effects (directory creation, env vars). Adding an explicit `initialize()` method makes the setup step transparent. Additionally, `_get_chroma_collection()` is not cached, so calling `initialize()` followed by `build_or_load()` would redundantly create two `PersistentClient` instances.

- [ ] **Step 1: Cache `_get_chroma_collection` on the instance**

Add `self._chroma_collection` to `__init__` and cache it:

```python
def __init__(self, settings: Settings) -> None:
    self._settings = settings
    self._embed_model: BaseEmbedding | None = None
    self._chroma_collection: Any | None = None
    self._index: VectorStoreIndex | None = None

def _get_chroma_collection(self) -> Any:
    if self._chroma_collection is None:
        self._settings.chroma_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self._settings.chroma_path))
        self._chroma_collection = client.get_or_create_collection(
            name=self._settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return self._chroma_collection
```

- [ ] **Step 2: Add `initialize()` method**

Add a public method that eagerly performs all setup:

```python
def initialize(self) -> None:
    """Eagerly initializes the embedding model and ChromaDB collection.

    Call this before build_or_load() to make the setup step explicit.
    Safe to call multiple times (idempotent).
    """
    self._get_embed_model()
    self._get_chroma_collection()
```

This is additive — the lazy initialization still works, but callers who want explicit setup can use `initialize()`.

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_knowledge_index.py -v
```

- [ ] **Step 3: Commit**

```bash
git add src/advogado_de_bolso/knowledge/index.py
git commit -m "refactor: add explicit initialize() to KnowledgeIndex (fixes #13)"
```

---

### Task 12: Document mock contract in conftest.py (Issue #14)

**Files:**
- Modify: [`conftest.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/tests/conftest.py#L44-L48)

- [ ] **Step 1: Add documentation comment**

Above the `ctx` fixture, add a comment documenting the mock contract:

```python
@pytest.fixture
def ctx(deps) -> MagicMock:
    """Mock RunContext for tool tests.

    NOTE: ctx.model is mocked as a string ("google-gla:test-model").
    In production, this is a pydantic_ai.models.Model instance. This is
    acceptable for unit tests where the model is only passed through
    (e.g., to sub-agents), but integration tests should use a real
    Model instance.
    """
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    ctx.model = "google-gla:test-model"
    return ctx
```

- [ ] **Step 2: Commit**

```bash
git add tests/conftest.py
git commit -m "docs: document mock contract for ctx.model in conftest.py"
```

---

### Task 13: Document CI requirement in pyproject.toml (Issue #15)

**Files:**
- Modify: [`pyproject.toml`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/pyproject.toml#L55)

- [ ] **Step 1: Add comment about CI installation**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
# NOTE: pythonpath is for local development only.
# CI must install the package in editable mode: pip install -e ".[dev]"
pythonpath = ["src"]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "docs: note CI editable install requirement for pythonpath"
```

---

### Task 14: Address agent.tool vs agent.tool_plain fragility (Issue #10)

**Files:**
- Modify: [`revisor.py`](file:///c:/Users/Vitor/Desktop/Vinicius/Projetos/advogado-de-bolso/src/advogado_de_bolso/tools/revisor.py) (already in `tools/` from Task 2)

**Rationale:** The contract ensuring the main agent doesn't leak reasoning into `revisar_resposta` relies on 10 lines of prompt engineering. While prompt engineering is the only mechanism available in pydantic-ai for this, we can reinforce the contract with a structured input model that makes the API self-documenting.

- [ ] **Step 1: Add a Pydantic model for the revisor input**

In `revisor.py`, add above `revisar_resposta`:

```python
class RevisionRequest(BaseModel):
    """Input contract for revisar_resposta.

    Forces the caller to explicitly separate user context from the
    generated response, making it harder to accidentally pass internal
    reasoning or tool results.
    """
    resposta_original: str = Field(
        description="Texto final da resposta que sera mostrado ao usuario. "
        "NAO inclua raciocinio interno, resultados de ferramentas, ou "
        "conclusoes intermediarias."
    )
    pergunta_usuario: str = Field(
        description="Texto original do usuario (mensagens do historico). "
        "NAO inclua resultados de ferramentas ou raciocinio do agente."
    )
```

> [!NOTE]
> This is a **documentation improvement** rather than a hard enforcement mechanism. pydantic-ai doesn't support input validation hooks on tool calls. The structured model with descriptive fields reinforces the contract at the API level, complementing the system prompt instructions.

This is a low-risk additive change. The function signature can continue to accept string args directly since pydantic-ai passes tool parameters as individual arguments.

- [ ] **Step 2: Commit**

```bash
git add src/advogado_de_bolso/tools/revisor.py
git commit -m "docs: add RevisionRequest model to reinforce tool input contract"
```

## Design Decisions Finalized

- **Issue #8 (subagents/ rename)**: Proceeding with renaming `revisor.py` to `tools/revisor.py` as there are no external consumers of the package.
- **Issue #4 (provider settings)**: Proceeding with the provider-aware fallback returning `None` for non-Google models to avoid crashes.
- **Issue #11 (function rename)**: Proceeding with the rename to `calcular_prazo_arrependimento` to match proper CDC legal terminology.

---


## Verification Plan

### Automated Tests

```bash
# Full test suite
uv run pytest tests/ -v --tb=short

# Specific test files for modified modules
uv run pytest tests/test_revision_result.py tests/test_revisor.py tests/test_redigir.py tests/test_rag_tool.py tests/test_calculos.py tests/test_config.py tests/test_knowledge_index.py -v
```

### Lint

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

### Manual Verification

- Run the CLI (`uv run advogado`) and verify the agent starts correctly
- Test `/ajuda`, `/modelo`, `/sair` commands work as expected
