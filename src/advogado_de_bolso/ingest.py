"""Script de ingestao: indexa os documentos de DATA_PATH no ChromaDB.

Uso:
    python -m advogado_de_bolso.ingest
"""

from __future__ import annotations

import logging
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from advogado_de_bolso.config import get_settings
from advogado_de_bolso.knowledge.index import KnowledgeIndex
from advogado_de_bolso.knowledge.loader import load_documents

logger = logging.getLogger(__name__)
console = Console()


def main() -> None:
    settings = get_settings()
    data_path: Path = settings.data_path

    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)

    files = [
        p
        for p in data_path.rglob("*")
        if p.is_file() and p.suffix.lower() in {".pdf", ".md", ".markdown", ".html", ".htm", ".txt"}
    ]
    if not files:
        console.print(
            Panel(
                f"[yellow]Nenhum documento suportado encontrado em {data_path}.[/yellow]\n\n"
                "Coloque arquivos PDF, HTML, Markdown ou TXT nessa pasta e rode novamente.\n"
                "Extensoes suportadas: .pdf, .md, .markdown, .html, .htm, .txt",
                title="Base vazia",
                border_style="yellow",
            )
        )
        return

    console.print(f"Carregando documentos de [bold]{data_path}[/bold]...")
    documents = load_documents(data_path)
    if not documents:
        console.print("[yellow]Nenhum documento valido encontrado.[/yellow]")
        return

    console.print(f"Encontrados [bold]{len(documents)}[/bold] documento(s).")

    knowledge = KnowledgeIndex(settings)
    knowledge.replace_documents(documents)

    console.print(
        Panel.fit(
            f"[green]Ingestao concluida![/green]\n"
            f"Documentos indexados: {len(documents)}\n"
            f"Indice persistido em: {settings.chroma_path}",
            border_style="green",
        )
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
