from __future__ import annotations

import importlib
from typing import Iterable

from sqlalchemy import text


MIGRATIONS = (
    "migrations.001_baseline",
    "migrations.002_sync_state",
    "migrations.003_reliability_foundations",
    "migrations.004_semantic_undo_inverse_metadata",
    "migrations.005_normalize_giocatore_team_refs",
    "migrations.006_operation_snapshot",
    "migrations.007_integer_economic_values",
    "migrations.008_stagioni",
)


def ensure_migrations_table(connection):
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                revision VARCHAR PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def applied_revisions(connection) -> set:
    rows = connection.execute(text("SELECT revision FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def run_migrations(engine, migrations: Iterable[str] = MIGRATIONS) -> list:
    """Run pending schema migrations and return applied revision ids."""
    applied_now = []
    with engine.begin() as connection:
        ensure_migrations_table(connection)
        applied = applied_revisions(connection)
        for module_name in migrations:
            module = importlib.import_module(module_name)
            revision = module.revision
            if revision in applied:
                continue
            module.upgrade(connection)
            connection.execute(
                text("INSERT INTO schema_migrations (revision) VALUES (:revision)"),
                {"revision": revision},
            )
            applied_now.append(revision)
    return applied_now
