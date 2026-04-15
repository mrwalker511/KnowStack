"""CLI: knowstack inspect — explore graph nodes, edges, and paths."""
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree

from knowstack.config.loader import load_config
from knowstack.retrieval.query_engine import QueryEngine

app = typer.Typer(help="Inspect nodes, edges, and paths in the knowledge graph.")
console = Console()


@app.command("node")
def inspect_node(
    symbol: str = typer.Argument(..., help="Symbol name or FQN to inspect."),
    repo_path: Path = typer.Option(Path("."), "--repo"),
    depth: int = typer.Option(1, "--depth", "-d", help="Neighbourhood depth."),
) -> None:
    """Inspect a single node and its immediate neighbours.

    [bold]Examples:[/bold]
        knowstack inspect node AuthService
        knowstack inspect node "src.auth.service.AuthService" --depth 2
    """
    config = load_config(repo_path=repo_path)
    with QueryEngine(config) as engine:
        # Find the anchor node
        result = engine.query_dsl(f'FIND * WHERE name = "{symbol}"')
        if not result.nodes:
            result = engine.query_dsl(f'FIND * WHERE fqn = "{symbol}"')

        if not result.nodes:
            console.print(f"[red]No node found for:[/red] {symbol}")
            raise typer.Exit(1)

        node = result.nodes[0]
        _print_node_panel(node)

        # Neighbours
        neighbours = engine._graph.neighbourhood(node.node_id, depth=depth, limit=30)
        if neighbours:
            tree = Tree(f"[bold]{node.fqn}[/bold] neighbourhood (depth={depth})")
            for n in neighbours:
                tree.add(f"[cyan]{n.node_type}[/cyan] {n.fqn} [dim]{n.file_path}[/dim]")
            console.print(tree)


@app.command("path")
def inspect_path(
    src: str = typer.Argument(..., help="Source symbol name or FQN."),
    dst: str = typer.Argument(..., help="Destination symbol name or FQN."),
    repo_path: Path = typer.Option(Path("."), "--repo"),
    max_depth: int = typer.Option(6, "--max-depth"),
) -> None:
    """Show call/import paths between two symbols.

    [bold]Example:[/bold]
        knowstack inspect path login database
    """
    config = load_config(repo_path=repo_path)
    with QueryEngine(config) as engine:
        result = engine.query_path(src, dst, max_depth=max_depth)

        if not result.paths:
            console.print(f"[yellow]No path found between[/yellow] {src!r} [yellow]and[/yellow] {dst!r}")
            return

        for i, path in enumerate(result.paths, 1):
            console.print(f"\n[bold]Path {i}:[/bold]")
            tree = Tree(f"[green]{path[0].fqn if path else src}[/green]")
            node = tree
            for step in path[1:]:
                node = node.add(f"[cyan]{step.node_type}[/cyan] {step.fqn} [dim]{step.file_path}[/dim]")
            console.print(tree)


@app.command("stats")
def inspect_stats(
    repo_path: Path = typer.Option(Path("."), "--repo"),
) -> None:
    """Show graph statistics."""
    from rich.table import Table
    config = load_config(repo_path=repo_path)
    from knowstack.graph.store import GraphStore
    store = GraphStore(config.db_path)

    t = Table(title="Graph Statistics")
    t.add_column("Entity", style="bold")
    t.add_column("Count", justify="right")

    for table in ["File", "Class", "Function", "Method", "Interface",
                  "TypeAlias", "ApiEndpoint", "DbModel", "Test", "ConfigFile"]:
        count = store.node_count(table)
        if count > 0:
            t.add_row(table, str(count))

    t.add_row("[dim]Total nodes[/dim]", str(store.node_count()))
    t.add_row("[dim]Total edges[/dim]", str(store.edge_count()))
    console.print(t)
    store.close()


def _print_node_panel(node: object) -> None:
    lines = [
        f"[bold]FQN:[/bold]      {node.fqn}",  # type: ignore[attr-defined]
        f"[bold]Type:[/bold]     {node.node_type}",
        f"[bold]File:[/bold]     {node.file_path}:{node.start_line}",
        f"[bold]Language:[/bold] {node.language}",
    ]
    if node.signature:  # type: ignore[attr-defined]
        lines.append(f"[bold]Signature:[/bold] [dim]{node.signature}[/dim]")
    if node.docstring:  # type: ignore[attr-defined]
        lines.append(f"[bold]Doc:[/bold]      [italic]{node.docstring[:200]}[/italic]")
    lines.append(f"[bold]Score:[/bold]    {node.importance_score:.4f}")
    console.print(Panel("\n".join(lines), title=f"[cyan]{node.name}[/cyan]"))
