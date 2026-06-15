"""Interactive CLI for Advogado de Bolso (batch 5).

The CLI is reviewer-gated with buffered streaming: generated tokens are
accumulated internally while the user sees a spinner, then the reviewer
runs, and only an approved turn is displayed and persisted.

The CLI does NOT use `ChatService` (per spec). It writes case files via
the storage layer directly (`cases.save(case, cases_path=...)`), with
its own reviewer gate around the streamed agent output.

CLI/API concurrent write limitation
-----------------------------------
The storage layer uses atomic replacement (unique same-directory temp
file + `os.replace`) which prevents torn JSON, but does NOT prevent
cross-process read-modify-write lost updates. Concurrent API and CLI
edits to the same case are explicitly unsupported and use
last-writer-wins semantics. The CLI never reads from disk during the
REPL — it only writes after each approved turn — so this is only a
concern if the user starts the CLI against a `cases_path` that the API
is concurrently writing to.

Testing surface
---------------
The Rich UI loop is hard to unit-test in isolation. To make the
business logic testable, this module exposes a small async helper

    _process_turn(agent, user_input, case, settings, reviewer_fn, deps) -> TurnResult

that streams the agent's response into an internal accumulator, runs
the reviewer, and returns a `TurnResult` describing what the loop
should render and persist. The tests in `tests/test_cli.py` exercise
`_process_turn` directly with a fake agent.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from prompt_toolkit import PromptSession
from pydantic_ai.messages import ModelMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from advogado_de_bolso.agent import build_agent
from advogado_de_bolso.config import Settings, get_settings
from advogado_de_bolso.deps import Deps
from advogado_de_bolso.knowledge.index import KnowledgeIndex
from advogado_de_bolso.schemas import ChatMessage, IconName, ResponseStyle
from advogado_de_bolso.storage import cases
from advogado_de_bolso.storage.cases import Case
from advogado_de_bolso.tools.revisor import RevisionResult, review_response

logger = logging.getLogger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REVIEW_BLOCKED_MESSAGE = (
    "Nao foi possivel validar esta resposta com seguranca. "
    "Tente reformular a pergunta ou procure o PROCON, a Defensoria Publica "
    "ou um advogado de confianca."
)

CLI_CASE_TITLE = "Consulta via CLI"
CLI_CASE_ICON: IconName = "gavel"
CLI_CASE_STYLE: ResponseStyle = "detalhado"
RESPONSE_TITLE = "[bold blue]Advogado de Bolso[/bold blue]"


# ---------------------------------------------------------------------------
# Time helpers (mirrored from service.py to keep the CLI module
# self-contained — the service module's helpers are underscored-private)
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _now_ms() -> int:
    """Integer milliseconds since the Unix epoch."""
    return time.time_ns() // 1_000_000


# ---------------------------------------------------------------------------
# Case factory
# ---------------------------------------------------------------------------


def _new_cli_case() -> Case:
    """Create a fresh CLI in-memory case with the canonical defaults.

    Used at CLI startup and on `/limpar`. The UUID is regenerated each
    call; the CLI loop never overwrites the previously saved case file
    on a `/limpar` (it just starts a new in-memory conversation).
    """
    now = _now()
    return Case(
        id=str(uuid.uuid4()),
        title=CLI_CASE_TITLE,
        icon_name=CLI_CASE_ICON,
        response_style=CLI_CASE_STYLE,
        is_demo=False,
        created_at=now,
        updated_at=now,
        chat_history=[],
        model_history=[],
    )


# ---------------------------------------------------------------------------
# Turn processing (the testable surface)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnResult:
    """Outcome of a single CLI turn produced by `_process_turn`.

    Pure data: the CLI loop applies the result (renders, appends to
    case, saves to disk). `_process_turn` itself does not mutate the
    case or write to disk.

    On an approved turn, `displayed_prose` is the accumulated agent
    text, `new_messages` is the `result.new_messages()` (current turn
    only — never `result.all_messages()`), and `new_chat_messages` is
    the `(user, assistant)` tuple to append to `case.chat_history`.
    On a blocked turn, `blocked` is `True`, `block_message` is the
    user-facing review-blocked text, and the three persistable fields
    are empty.
    """

    displayed_prose: str = ""
    block_message: str | None = None
    blocked: bool = False
    new_messages: list[ModelMessage] = field(default_factory=list)
    new_chat_messages: tuple[ChatMessage, ChatMessage] | None = None


async def _process_turn(
    agent: Any,
    user_input: str,
    case: Case,
    settings: Settings,
    reviewer_fn: Any,
    deps: Deps,
) -> TurnResult:
    """Stream a single turn, run the reviewer, and return a TurnResult.

    The CLI's spinner/live UI wraps this call. Tokens are accumulated
    internally (NOT displayed to the user) so the reviewer can gate the
    final prose. The returned `TurnResult` is what the loop should
    render and persist.

    `reviewer_fn` is the async review function (or a mock). It is
    invoked with keyword arguments `question`, `response`, `model`,
    and `model_settings`; the test suite asserts those four args are
    passed correctly.
    """
    accumulated = ""
    async with agent.run_stream(
        user_input,
        deps=deps,
        message_history=case.model_history,
    ) as result:
        async for chunk in result.stream_text(delta=True):
            accumulated += chunk
        new_messages = result.new_messages()

    revision: RevisionResult = await reviewer_fn(
        question=user_input,
        response=accumulated,
        model=settings.full_model_name,
        model_settings=settings.build_model_settings(),
    )

    if not revision.approved_as_is:
        return TurnResult(
            block_message=REVIEW_BLOCKED_MESSAGE,
            blocked=True,
        )

    user_ts = _now_ms()
    assistant_ts = user_ts + 1
    user_msg = ChatMessage(
        id=f"user-{user_ts}",
        sender="user",
        text=user_input,
        timestamp=user_ts,
    )
    assistant_msg = ChatMessage(
        id=f"assistant-{assistant_ts}",
        sender="assistant",
        text=accumulated,
        timestamp=assistant_ts,
    )

    return TurnResult(
        displayed_prose=accumulated,
        new_messages=new_messages,
        new_chat_messages=(user_msg, assistant_msg),
        blocked=False,
    )


# ---------------------------------------------------------------------------
# Slash commands and welcome
# ---------------------------------------------------------------------------


def _build_commands_help() -> str:
    return (
        "[bold]Comandos disponiveis:[/bold]\n"
        "  /sair, /exit           Encerrar o chat\n"
        "  /limpar, /clear        Iniciar uma nova consulta (novo UUID)\n"
        "  /ajuda, /help          Mostrar esta ajuda\n"
        "  /modelo                Mostrar modelo e configuracoes"
    )


COMMANDS_HELP = _build_commands_help()


def _render_welcome(settings: Settings) -> None:
    console.print(
        Panel.fit(
            "[bold blue]Advogado de Bolso[/bold blue]\n"
            "Assistente de direitos do consumidor brasileiro\n\n"
            f"Modelo: [dim]{settings.llm_model}[/dim]  |  "
            f"Thinking: [dim]{settings.thinking_level or 'off'}[/dim]  |  "
            f"Embedding: [dim]{settings.embedding_model}[/dim]\n\n"
            "Digite [bold]/ajuda[/bold] para ver comandos ou [bold]/sair[/bold] para sair.",
            border_style="blue",
            title="Bem-vindo",
        )
    )


def _check_config(settings: Settings) -> bool:
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


def _print_model_info(settings: Settings) -> None:
    console.print(
        f"Modelo LLM:     {settings.llm_model}\n"
        f"Thinking level: {settings.thinking_level or 'off'}\n"
        f"Embedding:      {settings.embedding_model}\n"
        f"Collection:     {settings.collection_name}\n"
        f"Data path:      {settings.data_path}\n"
        f"Cases path:     {settings.cases_path}"
    )


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------


async def _run_chat_loop() -> None:
    settings = get_settings()

    if not _check_config(settings):
        sys.exit(1)

    with console.status("[bold green]Carregando base de conhecimento..."):
        knowledge = KnowledgeIndex(settings)
        try:
            knowledge.build_or_load()
        except Exception as e:
            console.print(
                Panel(
                    f"[red]Erro ao carregar indice:[/red]\n{e}",
                    title="Erro",
                    border_style="red",
                )
            )
            sys.exit(1)

    retriever = knowledge.as_retriever()
    agent = build_agent(settings)
    deps = Deps(settings=settings, retriever=retriever)

    async def _reviewer_fn(**kwargs: Any) -> RevisionResult:
        return await review_response(**kwargs)

    case: Case = _new_cli_case()

    session: PromptSession[str] = PromptSession()

    _render_welcome(settings)

    while True:
        try:
            user_input = await session.prompt_async("Voce> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\nAte logo!")
            return

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd_key = user_input.lower().split()[0]
            if cmd_key in ("/sair", "/exit"):
                console.print("Ate logo!")
                return
            if cmd_key in ("/limpar", "/clear"):
                console.print("[dim]Nova consulta iniciada.[/dim]")
                case = _new_cli_case()
                continue
            if cmd_key in ("/ajuda", "/help"):
                console.print(COMMANDS_HELP)
                continue
            if cmd_key == "/modelo":
                _print_model_info(settings)
                continue
            console.print(f"[red]Comando desconhecido:[/red] {user_input}")
            continue

        with console.status("[bold green]Pensando...", spinner="dots"):
            try:
                turn = await _process_turn(
                    agent, user_input, case, settings, _reviewer_fn, deps
                )
            except Exception as e:
                logger.exception("Erro durante o turno")
                console.print(
                    Panel(
                        f"[red]Erro:[/red] {e}",
                        title="Erro",
                        border_style="red",
                    )
                )
                continue

        if turn.blocked:
            console.print(
                Panel(
                    turn.block_message or "",
                    title="Resposta bloqueada",
                    border_style="red",
                )
            )
            continue

        console.print(Markdown(turn.displayed_prose))
        if turn.new_chat_messages is not None:
            case.chat_history.extend(turn.new_chat_messages)
        case.model_history = case.model_history + turn.new_messages
        case.updated_at = _now()
        cases.save(case, cases_path=settings.cases_path)


def app() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(_run_chat_loop())
    except KeyboardInterrupt:
        console.print("\nAte logo!")


if __name__ == "__main__":
    app()
