"""CLI interativo com loop de chat, streaming, memoria de sessao e comandos."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from prompt_toolkit import PromptSession
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from rich.console import Console, RenderableType
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from advogado_de_bolso.agent import build_agent
from advogado_de_bolso.config import get_settings
from advogado_de_bolso.deps import Deps
from advogado_de_bolso.knowledge.index import KnowledgeIndex

logger = logging.getLogger(__name__)
console = Console()

RESPONSE_TITLE = "[bold blue]Advogado de Bolso[/bold blue]"


@dataclass
class _Command:
    """A CLI command with aliases, help text, and handler."""

    aliases: tuple[str, ...]
    help_text: str
    handler: Callable[[Any, list[ModelMessage]], str | None]


def _handle_exit(_settings: Any, _message_history: list[ModelMessage]) -> str:
    console.print("Ate logo!")
    return "exit"


def _handle_clear(_settings: Any, message_history: list[ModelMessage]) -> None:
    message_history.clear()
    console.print("[dim]Historico da sessao limpo.[/dim]")


def _handle_help(_settings: Any, _message_history: list[ModelMessage]) -> None:
    console.print(COMMANDS_HELP)


def _handle_modelo(settings: Any, _message_history: list[ModelMessage]) -> None:
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

_CMD_LOOKUP: dict[str, _Command] = {}
for _cmd_def in _COMMANDS:
    for _alias in _cmd_def.aliases:
        _CMD_LOOKUP[_alias] = _cmd_def


def _build_commands_help() -> str:
    lines = ["[bold]Comandos disponiveis:[/bold]"]
    for cmd in _COMMANDS:
        aliases = ", ".join(cmd.aliases)
        lines.append(f"  {aliases:<20s} {cmd.help_text}")
    return "\n".join(lines)


COMMANDS_HELP = _build_commands_help()


def _render_welcome(settings: Any) -> None:
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


def _make_response_panel(content: RenderableType) -> Panel:
    return Panel(content, title=RESPONSE_TITLE, border_style="blue")


async def _stream_agent_response(
    agent: Agent[Deps, str],
    user_input: str,
    deps: Deps,
    message_history: list[ModelMessage],
) -> tuple[str, list[ModelMessage]] | None:
    """Roda o agente em modo streaming, exibindo a resposta em tempo real.

    Retorna (output_final, message_history_atualizado) ou None em caso de erro.
    """
    accumulated = ""

    def renderable() -> RenderableType:
        if not accumulated:
            return Spinner("dots", text="Pensando...")
        return Markdown(accumulated)

    with Live(_make_response_panel(renderable()), console=console, refresh_per_second=15) as live:
        try:
            async with agent.run_stream(
                user_input,
                deps=deps,
                message_history=message_history,
            ) as result:
                async for chunk in result.stream_text(delta=True):
                    accumulated += chunk
                    live.update(_make_response_panel(renderable()))
        except Exception as e:
            logger.exception("Erro durante streaming do agente")
            live.update(_make_response_panel(f"[red]Erro:[/red] {e}"))
            return None

    return accumulated, result.all_messages()


async def _run_chat_loop() -> None:
    settings = get_settings()

    if not _check_config():
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
    deps = Deps(
        settings=settings,
        retriever=retriever,
    )

    session: PromptSession[str] = PromptSession()

    _render_welcome(settings)

    message_history: list[ModelMessage] = []

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
            cmd_def = _CMD_LOOKUP.get(cmd_key)
            if cmd_def is None:
                console.print(f"[red]Comando desconhecido:[/red] {user_input}")
                continue
            result = cmd_def.handler(settings, message_history)
            if result == "exit":
                return
            continue

        outcome = await _stream_agent_response(agent, user_input, deps, message_history)
        if outcome is None:
            continue

        final_output, message_history = outcome
        console.print()  # newline after Live panel collapses


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
