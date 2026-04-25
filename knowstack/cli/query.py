"""CLI: knowstack query — query the knowledge graph."""
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from knowstack.config.loader import load_config
from knowstack.retrieval.query_engine import QueryEngine, QueryResult
from knowstack.utils.logging import setup_logging

app = typer.Typer(help="Query the knowledge graph.")
console = Console()


@app.callback(invoke_without_command=True)
def query(
    query_str: str | None = typer.Argument(
        None, help="DSL query or natural-language question."
    ),
    mode: str = typer.Option(
        "auto",
        "--mode", "-m",
        help="Query mode: auto | dsl | semantic | hybrid | impact | path | nl",
    ),
    repo_path: Path = typer.Option(Path("."), "--repo", help="Repository root."),
    top_k: int = typer.Option(20, "--top-k", "-k", help="Maximum results."),
    context: bool = typer.Option(
        False, "--context", "-c", help="Print packed LLM context block."
    ),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON."),
    interactive: bool = typer.Option(
        False, "--interactive", "-I", help="Interactive query REPL."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Query the knowledge graph with DSL or natural language.

    [bold]DSL examples:[/bold]
        knowstack query "FIND function WHERE tag = auth"
        knowstack query "DEPENDENTS UserService"
        knowstack query "IMPACT PaymentProcessor DEPTH 4"
        knowstack query "PATH FROM login TO database"

    [bold]Natural language:[/bold]
        knowstack query "How does authentication work?" --mode nl
        knowstack query "What calls the checkout function?" --mode semantic
    """
    setup_logging("DEBUG" if verbose else "WARNING")
    config = load_config(repo_path=repo_path)

    with QueryEngine(config) as engine:
        if interactive:
            _run_repl(engine, context)
            return

        if not query_str:
            console.print("[red]Provide a query string or --interactive[/red]")
            raise typer.Exit(1)

        result = _dispatch(engine, query_str, mode, top_k)

        if json_out:
            import json
            console.print_json(json.dumps(result.as_dict()))
        elif context:
            console.print(result.context)
        else:
            _print_table(result)


def _dispatch(engine: QueryEngine, q: str, mode: str, top_k: int) -> QueryResult:
    if mode == "dsl" or (mode == "auto" and _looks_like_dsl(q)):
        return engine.query_dsl(q)
    elif mode == "semantic":
        return engine.query_semantic(q, top_k=top_k)
    elif mode == "hybrid":
        return engine.query_hybrid(q, top_k=top_k)
    elif mode == "nl":
        return engine.query_nl(q)
    else:
        # auto: try semantic as default for natural-language
        return engine.query_semantic(q, top_k=top_k)


def _looks_like_dsl(q: str) -> bool:
    first = q.strip().split()[0].upper() if q.strip() else ""
    return first in {"FIND", "DEPENDENTS", "IMPACT", "PATH"}


def _print_table(result: object) -> None:
    if result.error:  # type: ignore[attr-defined]
        console.print(f"[red]Error:[/red] {result.error}")  # type: ignore[attr-defined]
        return

    t = Table(title=f"Results for: {result.query}", show_lines=False)  # type: ignore[attr-defined]
    t.add_column("#", style="dim", width=3)
    t.add_column("Type", style="cyan", width=12)
    t.add_column("FQN", style="bold", no_wrap=False)
    t.add_column("File", style="dim", no_wrap=False)
    t.add_column("Score", justify="right", width=6)

    for i, node in enumerate(result.nodes[:50], 1):  # type: ignore[attr-defined]
        t.add_row(
            str(i),
            node.node_type,
            node.fqn,
            f"{node.file_path}:{node.start_line}" if node.start_line else node.file_path,
            f"{node.final_score:.2f}",
        )

    console.print(t)
    console.print(f"[dim]{result.node_count} results[/dim]")  # type: ignore[attr-defined]


def _run_repl(engine: QueryEngine, show_context: bool) -> None:
    console.print("[bold]KnowStack Query REPL[/bold] — type [dim]exit[/dim] to quit")
    console.print("  DSL:  FIND function WHERE tag = auth")
    console.print("  NL:   how does authentication work?")
    console.print()

    while True:
        try:
            q = console.input("[bold cyan]❯ [/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]bye[/dim]")
            break

        if not q or q.lower() in {"exit", "quit", "q"}:
            break

        result = engine.query_semantic(q)
        if show_context:
            console.print(result.context)
        else:
            _print_table(result)
