"""Schema migration support for KnowStack.

When SCHEMA_VERSION is bumped, add a migration function here and register
it in MIGRATIONS. The GraphStore.initialize_schema() is idempotent (CREATE IF
NOT EXISTS), so most additive changes need no explicit migration.
"""
from __future__ import annotations

import logging

from .schema import SCHEMA_VERSION
from .store import GraphStore

log = logging.getLogger(__name__)

# Maps from_version -> migration callable
MIGRATIONS: dict[int, object] = {}


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
            fn(store)  # type: ignore[call-arg]
    store._set_meta("schema_version", str(SCHEMA_VERSION))
