"""CLI: knowstack workspace — manage multi-repo workspaces."""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from knowstack.utils.logging import setup_logging

app = typer.Typer(help="Manage multi-repo workspaces.")
console = Console()


def _load_ws(workspace_path: Path):
    from knowstack.workspace.config import WorkspaceConfig
    return WorkspaceConfig.load(workspace_path)


# ── knowstack workspace init ──────────────────────────────────────────────────

@app.command("init")
def workspace_init(
    path: Path = typer.Argument(Path("."), help="Directory to initialise as a workspace."),
) -> None:
    """Create a new workspace.toml in PATH."""
    from knowstack.workspace.config import WorkspaceConfig
    path = path.resolve()
    toml = path / "workspace.toml"
    if toml.exists():
        console.print(f"[yellow]workspace.toml already exists at {toml}[/yellow]")
        raise typer.Exit(1)
    WorkspaceConfig.init(path)
    console.print(f"[green]Workspace initialised:[/green] {toml}")


# ── knowstack workspace add ───────────────────────────────────────────────────

@app.command("add")
def workspace_add(
    repo_path: Path = typer.Argument(..., help="Path to the repository to add."),
    repo_id: Optional[str] = typer.Option(None, "--id", help="Unique repo identifier (default: directory name)."),
    workspace_path: Path = typer.Option(Path("."), "--workspace", "-w", help="Workspace directory."),
) -> None:
    """Add a repository to the workspace."""
    ws = _load_ws(workspace_path.resolve())
    try:
        entry = ws.add_repo(repo_path.resolve(), repo_id=repo_id)
        ws.save()
        console.print(f"[green]Added[/green] {entry.id}  →  {entry.path}")
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


# ── knowstack workspace remove ────────────────────────────────────────────────

@app.command("remove")
def workspace_remove(
    repo_id: str = typer.Argument(..., help="Repo identifier to remove."),
    workspace_path: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """Remove a repository from the workspace (does not delete indexed data)."""
    ws = _load_ws(workspace_path.resolve())
    try:
        ws.remove_repo(repo_id)
        ws.save()
        console.print(f"[yellow]Removed[/yellow] {repo_id}")
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)


# ── knowstack workspace list ──────────────────────────────────────────────────

@app.command("list")
def workspace_list(
    workspace_path: Path = typer.Option(Path("."), "--workspace", "-w"),
) -> None:
    """List all repositories in the workspace."""
    ws = _load_ws(workspace_path.resolve())
    if not ws.repos:
        console.print("[dim]No repos registered. Run: knowstack workspace add <path>[/dim]")
        return
    t = Table("ID", "Path", show_header=True, header_style="bold")
    for r in ws.repos:
        t.add_row(r.id, str(r.path))
    console.print(t)


# ── knowstack workspace index ─────────────────────────────────────────────────

@app.command("index")
def workspace_index(
    repo_id: Optional[str] = typer.Argument(None, help="Index only this repo (default: all)."),
    workspace_path: Path = typer.Option(Path("."), "--workspace", "-w"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Index all (or one) repository into the shared knowledge graph."""
    from knowstack.workspace.indexer import WorkspaceIndexer

    setup_logging("DEBUG" if verbose else "INFO")
    ws = _load_ws(workspace_path.resolve())

    console.rule("[bold]Workspace index[/bold]")
    indexer = WorkspaceIndexer(ws)
    reports = indexer.run(repo_id=repo_id)

    for rid, report in reports.items():
        status = "[green]✓[/green]" if not report.errors else "[yellow]⚠[/yellow]"
        console.print(
            f"  {status} [bold]{rid}[/bold]  "
            f"[dim]{report.files_parsed} files  "
            f"{report.nodes_written} nodes  "
            f"{report.edges_written} edges  "
            f"{report.duration_seconds:.1f}s[/dim]"
        )
        if report.errors and verbose:
            for e in report.errors[:5]:
                console.print(f"    [red]{e}[/red]")


# ── knowstack workspace query ─────────────────────────────────────────────────

@app.command("query")
def workspace_query(
    query: str = typer.Argument(..., help="DSL or natural-language query."),
    repo_id: Optional[str] = typer.Option(None, "--repo", "-r", help="Scope to a specific repo."),
    mode: str = typer.Option("auto", "--mode", "-m", help="Query mode: auto|dsl|semantic|nl|hybrid."),
    context: bool = typer.Option(False, "--context", "-c", help="Print LLM-ready context block."),
    workspace_path: Path = typer.Option(Path("."), "--workspace", "-w"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Query the workspace knowledge graph across all repos.

    [bold]Examples:[/bold]
        knowstack workspace query "FIND function WHERE tag = auth"
        knowstack workspace query "what calls authenticate?" --mode nl
        knowstack workspace query "DEPENDENTS PaymentService" --repo org/billing
    """
    from knowstack.config.schema import KnowStackConfig
    from knowstack.retrieval.query_engine import QueryEngine

    setup_logging("DEBUG" if verbose else "INFO")
    ws = _load_ws(workspace_path.resolve())

    config = KnowStackConfig(
        repo_path=ws.workspace_path,
        db_path=ws.db_path,
        vector_db_path=ws.vector_db_path,
    )

    with QueryEngine(config) as engine:
        if mode == "nl":
            result = engine.query_nl(query, repo_id=repo_id)
        elif mode == "semantic":
            result = engine.query_semantic(query, repo_id=repo_id)
        elif mode == "hybrid":
            result = engine.query_hybrid(query, repo_id=repo_id)
        else:
            # Auto: try DSL first, fall back to semantic
            dsl_keywords = ("FIND", "DEPENDENTS", "IMPACT", "PATH")
            if query.strip().upper().split()[0] in dsl_keywords:
                result = engine.query_dsl(query, repo_id=repo_id)
            else:
                result = engine.query_semantic(query, repo_id=repo_id)

        if context:
            console.print(result.context)
            return

        if not result.nodes:
            console.print("[dim]No results.[/dim]")
            return

        t = Table("Repo", "FQN", "Type", "File", show_header=True, header_style="bold")
        for n in result.nodes[:20]:
            t.add_row(n.repo_id or "—", n.fqn, n.node_type, n.file_path)
        console.print(t)
        if len(result.nodes) > 20:
            console.print(f"[dim]… {len(result.nodes) - 20} more results[/dim]")
