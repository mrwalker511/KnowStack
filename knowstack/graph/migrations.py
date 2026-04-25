"""Schema migration support for KnowStack.

When SCHEMA_VERSION is bumped, add a migration function here and register
it in MIGRATIONS. The GraphStore.initialize_schema() is idempotent (CREATE IF
NOT EXISTS), so most additive changes need no explicit migration.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from .schema import SCHEMA_VERSION
from .store import GraphStore

log = logging.getLogger(__name__)

_NODE_TABLES = [
    "File", "Directory", "Class", "Function", "Method",
    "Interface", "TypeAlias", "ApiEndpoint", "DbModel", "Test", "ConfigFile",
]


def _migrate_v2(store: GraphStore) -> None:
    """Add repo_id column to all node tables (multi-repo support)."""
    for table in _NODE_TABLES:
        try:
            store.cypher(f"ALTER TABLE {table} ADD repo_id STRING DEFAULT \"\"")
            log.debug("Added repo_id to %s", table)
        except Exception:
            pass  # Column already exists in fresh installs


# Maps from_version -> migration callable
MIGRATIONS: dict[int, Callable[[GraphStore], None]] = {
    2: _migrate_v2,
}


def migrate(store: GraphStore) -> None:
    """Apply any pending schema migrations in order."""
    current = store.schema_version()
    if current == SCHEMA_VERSION:
        return
    if current > SCHEMA_VERSION:
        log.warning(
            "DB schema version %d is newer than code version %d — "
            "downgrade is not supported.",
            current,
            SCHEMA_VERSION,
        )
        return
    for version in range(current + 1, SCHEMA_VERSION + 1):
        fn = MIGRATIONS.get(version)
        if fn is None:
            log.debug("No migration for version %d — skipping", version)
        else:
            log.info("Applying schema migration to version %d", version)
            fn(store)
    store._set_meta("schema_version", str(SCHEMA_VERSION))
