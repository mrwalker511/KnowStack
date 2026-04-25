"""CLI: knowstack index — run the ingestion pipeline."""
from pathlib import Path

import typer
from rich.console import Console

from knowstack.config.loader import load_config
from knowstack.config.schema import KnowStackConfig
from knowstack.ingestion.pipeline import IngestionPipeline
from knowstack.utils.logging import setup_logging

app = typer.Typer(help="Index a repository into the knowledge graph.")
console = Console()


@app.callback(invoke_without_command=True)
def index(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to index.",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    db_path: Path | None = typer.Option(
        None, "--db", help="Override path to the Kuzu graph database."
    ),
    incremental: bool = typer.Option(
        False, "--incremental", "-i", help="Only re-index changed files."
    ),
    workers: int = typer.Option(
        4, "--workers", "-w", help="Number of parallel parser processes."
    ),
    no_embed: bool = typer.Option(
        False, "--no-embed", help="Skip embedding step (graph-only)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Index [dim]REPO_PATH[/dim] into a queryable knowledge graph.

    [bold]Examples:[/bold]
        knowstack index .
        knowstack index ~/projects/myapp --incremental
        knowstack index ~/projects/myapp --db /tmp/myapp.kuzu
    """
    setup_logging("DEBUG" if verbose else "INFO")
    overrides: dict[str, object] = {}
    if db_path:
        overrides["db_path"] = str(db_path)
    overrides["parse_workers"] = workers

    config = load_config(repo_path=repo_path, overrides=overrides)
    config = config.model_copy(update={"repo_path": repo_path.resolve()})

    console.rule(f"[bold]Indexing[/bold] {repo_path.resolve()}")

    if incremental:
        _run_incremental(config)
    else:
        pipeline = IngestionPipeline(config)
        report = pipeline.run(show_progress=True)
        _print_report(report)


def _run_incremental(config: KnowStackConfig) -> None:
    try:
        from knowstack.graph.store import GraphStore
        from knowstack.incremental.change_detector import ChangeDetector
        from knowstack.incremental.partial_pipeline import PartialPipeline

        store = GraphStore(config.db_path)
        detector = ChangeDetector(config.repo_path, store)
        change_set = detector.detect()
        console.print(
            f"Changes: [green]+{len(change_set.added)}[/green] "
            f"[yellow]~{len(change_set.modified)}[/yellow] "
            f"[red]-{len(change_set.deleted)}[/red]"
        )
        if change_set.is_empty():
            console.print("[green]Nothing to re-index.[/green]")
            return
        partial = PartialPipeline(config, store)
        report = partial.run(change_set)
        _print_report(report)
        store.close()
    except ImportError as exc:
        console.print(f"[red]Incremental indexing not available: {exc}[/red]")


def _print_report(report: object) -> None:
    console.print()
    console.print(
        f"[bold green]Done[/bold green] in {report.duration_seconds:.1f}s  "  # type: ignore[attr-defined]
        f"[dim]{report.files_parsed} files  "
        f"{report.nodes_written} nodes  "
        f"{report.edges_written} edges  "
        f"{report.nodes_embedded} embedded[/dim]"
    )
    if report.errors:  # type: ignore[attr-defined]
        console.print(f"[yellow]{len(report.errors)} warnings — run with --verbose to see them[/yellow]")  # type: ignore[attr-defined]
