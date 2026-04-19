"""Benchmark: full index vs. incremental re-index performance.

Usage:
    python tests/benchmarks/bench_incremental.py
    python tests/benchmarks/bench_incremental.py --sizes 10,50,100 --changes 5
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# Ensure project root is on the path when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from knowstack.config.schema import KnowStackConfig
from knowstack.graph.store import GraphStore
from knowstack.incremental.change_detector import ChangeDetector
from knowstack.incremental.partial_pipeline import PartialPipeline
from knowstack.ingestion.pipeline import IngestionPipeline


@dataclass
class BenchResult:
    repo_size: int
    full_index_s: float
    incremental_s: float
    nodes_full: int
    nodes_incremental: int
    files_changed: int

    @property
    def speedup(self) -> float:
        return self.full_index_s / self.incremental_s if self.incremental_s > 0 else float("inf")


class SyntheticRepoBuilder:
    """Generates and mutates a synthetic Python repository for benchmarking."""

    @staticmethod
    def build(repo_dir: Path, n_files: int, fns_per_file: int = 10) -> None:
        repo_dir.mkdir(parents=True, exist_ok=True)
        for i in range(n_files):
            funcs = "\n\n".join(
                f'def func_{i}_{j}(x: int) -> str:\n'
                f'    """Function {j} in module {i}."""\n'
                f'    return str(x + {j})'
                for j in range(fns_per_file)
            )
            code = f'"""Generated module {i}."""\n\n{funcs}\n'
            (repo_dir / f"generated_module_{i}.py").write_text(code)

    @staticmethod
    def mutate(repo_dir: Path, n_files: int) -> list[Path]:
        """Overwrite N random files with slightly different content. Returns changed paths."""
        all_py = list(repo_dir.glob("generated_module_*.py"))
        targets = random.sample(all_py, min(n_files, len(all_py)))
        for path in targets:
            original = path.read_text()
            path.write_text(original + "\n# mutated\n")
        return targets


def _make_config(repo_dir: Path, db_path: Path, vector_path: Path) -> KnowStackConfig:
    return KnowStackConfig(
        repo_path=repo_dir,
        db_path=db_path,
        vector_db_path=str(vector_path),
        enable_git_enrichment=False,
        embedding_model="BAAI/bge-small-en-v1.5",
    )


def bench_full_index(repo_dir: Path, work_dir: Path) -> tuple[float, int]:
    """Time a full re-index. Returns (seconds, nodes_written)."""
    config = _make_config(repo_dir, work_dir / "graph.kuzu", work_dir / "vectors")
    t0 = time.monotonic()
    report = IngestionPipeline(config).run(show_progress=False)
    elapsed = time.monotonic() - t0
    return elapsed, report.nodes_written


def bench_incremental(repo_dir: Path, work_dir: Path, n_changes: int) -> tuple[float, int, int]:
    """
    Time an incremental run after mutating n_changes files.
    Returns (seconds, nodes_written, files_changed).
    Assumes work_dir already has a full index (graph.kuzu + vectors).
    """
    changed = SyntheticRepoBuilder.mutate(repo_dir, n_changes)
    config = _make_config(repo_dir, work_dir / "graph.kuzu", work_dir / "vectors")

    t0 = time.monotonic()
    with GraphStore(config.db_path) as store:
        cs = ChangeDetector(repo_dir, store).detect()
        report = PartialPipeline(config, store).run(cs)
    elapsed = time.monotonic() - t0
    return elapsed, report.nodes_written, len(changed)


def run_benchmark(sizes: list[int], n_changes: int, fns_per_file: int, warmup: bool) -> list[BenchResult]:
    results: list[BenchResult] = []

    for size in sizes:
        tmpdir = tempfile.mkdtemp(prefix=f"knowstack_bench_{size}_")
        try:
            repo_dir = Path(tmpdir) / "repo"
            full_work = Path(tmpdir) / "full_db"
            inc_work = Path(tmpdir) / "inc_db"
            full_work.mkdir()
            inc_work.mkdir()

            SyntheticRepoBuilder.build(repo_dir, n_files=size, fns_per_file=fns_per_file)

            if warmup:
                # Warmup run (model download, JIT etc) — not reported
                _warmup_dir = Path(tmpdir) / "warmup"
                _warmup_dir.mkdir()
                bench_full_index(repo_dir, _warmup_dir)
                shutil.rmtree(str(_warmup_dir))

            # Full index
            full_s, nodes_full = bench_full_index(repo_dir, full_work)

            # Set up incremental baseline: copy DB from full index
            shutil.copytree(str(full_work), str(inc_work), dirs_exist_ok=True)
            shutil.copytree(str(repo_dir), str(Path(tmpdir) / "inc_repo"))
            inc_repo = Path(tmpdir) / "inc_repo"

            inc_s, nodes_inc, n_changed = bench_incremental(inc_repo, inc_work, n_changes)

            results.append(BenchResult(
                repo_size=size,
                full_index_s=full_s,
                incremental_s=inc_s,
                nodes_full=nodes_full,
                nodes_incremental=nodes_inc,
                files_changed=n_changed,
            ))

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return results


def print_table(results: list[BenchResult]) -> None:
    print()
    print(f"{'Repo (files)':>12} | {'Changes':>7} | {'Full index':>10} | {'Incremental':>11} | {'Speedup':>7} | {'Nodes (full)':>12}")
    print("-" * 72)
    for r in results:
        print(
            f"{r.repo_size:>12} | {r.files_changed:>7} | {r.full_index_s:>9.1f}s | "
            f"{r.incremental_s:>10.2f}s | {r.speedup:>6.1f}x | {r.nodes_full:>12}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark full vs. incremental KnowStack indexing")
    parser.add_argument("--sizes", default="10,50", help="Comma-separated repo sizes (number of files)")
    parser.add_argument("--changes", type=int, default=3, help="Files to mutate between runs")
    parser.add_argument("--fns-per-file", type=int, default=5, help="Functions per generated file")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warmup run")
    args = parser.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",")]
    warmup = not args.no_warmup

    print(f"KnowStack incremental benchmark — sizes={sizes}, changes={args.changes}")
    if warmup:
        print("(Running warmup for first size to prime the embedding model…)")

    results = run_benchmark(
        sizes=sizes,
        n_changes=args.changes,
        fns_per_file=args.fns_per_file,
        warmup=warmup,
    )
    print_table(results)


if __name__ == "__main__":
    main()
