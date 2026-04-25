"""KnowStack CLI root command group."""
import typer
from rich.console import Console

from knowstack import __version__

app = typer.Typer(
    name="knowstack",
    help="Codebase knowledge graph — index, query, and explore any repository.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"KnowStack [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-V", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    )
) -> None:
    """KnowStack — turn any codebase into a queryable knowledge graph."""


# Register sub-commands
from knowstack.cli import index, inspect, query, serve, workspace  # noqa: E402

app.add_typer(index.app, name="index")
app.add_typer(query.app, name="query")
app.add_typer(inspect.app, name="inspect")
app.add_typer(serve.app, name="serve")
app.add_typer(workspace.app, name="workspace")
