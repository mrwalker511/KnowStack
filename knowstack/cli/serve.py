"""CLI: knowstack serve — start the HTTP API server."""
from pathlib import Path

import typer
from rich.console import Console

from knowstack.config.loader import load_config
from knowstack.utils.logging import setup_logging

app = typer.Typer(help="Serve the knowledge graph over HTTP (requires knowstack[serve]).")
console = Console()


@app.callback(invoke_without_command=True)
def serve(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the indexed repository.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev only)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start the KnowStack HTTP API server for [dim]REPO_PATH[/dim].

    [bold]Examples:[/bold]
        knowstack serve .
        knowstack serve ~/projects/myapp --port 9000
        knowstack serve . --host 0.0.0.0

    Requires: pip install knowstack[serve]

    [dim]Docs available at http://HOST:PORT/docs once running.[/dim]
    """
    try:
        import uvicorn
    except ImportError:
        console.print(
            "[red]uvicorn not installed.[/red] "
            "Run: [bold]pip install knowstack\\[serve][/bold]"
        )
        raise typer.Exit(1)

    try:
        from knowstack.serve.app import create_app
    except ImportError:
        console.print(
            "[red]FastAPI not installed.[/red] "
            "Run: [bold]pip install knowstack\\[serve][/bold]"
        )
        raise typer.Exit(1)

    setup_logging("DEBUG" if verbose else "INFO")
    config = load_config(repo_path=repo_path)
    config = config.model_copy(update={"repo_path": repo_path.resolve()})

    console.rule(f"[bold]KnowStack API[/bold] — {repo_path.resolve()}")
    console.print(f"  [dim]http://{host}:{port}/docs[/dim]")
    console.print()

    fastapi_app = create_app(config)
    uvicorn.run(fastapi_app, host=host, port=port, reload=reload)
