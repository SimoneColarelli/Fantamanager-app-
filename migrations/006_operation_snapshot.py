"""Add uniform operation snapshots."""

from __future__ import annotations

import json

from sqlalchemy import text


revision = "006_operation_snapshot"


def _table_exists(connection, table_name: str) -> bool:
    return bool(
        connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type = 'table' AND name = :table_name
                """
            ),
            {"table_name": table_name},
        ).scalar()
    )


def _columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _legacy_payload(row) -> str:
    legacy_players = []
    if row["giocatori_snapshot"]:
        try:
            parsed = json.loads(row["giocatori_snapshot"])
            if isinstance(parsed, list):
                legacy_players = parsed
        except json.JSONDecodeError:
            legacy_players = []

    payload = {
        "schema_version": 1,
        "source": "legacy_migration",
        "tipo_operazione": row["tipo_operazione"],
        "data": row["data"],
        "clausole": row["clausole"] or "",
        "conguaglio": row["conguaglio"] or 0,
        "conguaglio_da_id": row["conguaglio_da_id"],
        "fantasquadre": {
            "a": {"id": row["fantasquadra_a_id"]},
            "b": {"id": row["fantasquadra_b_id"]},
        },
        "giocatori": legacy_players,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def upgrade(connection):
    if not _table_exists(connection, "operazioni"):
        return

    columns = _columns(connection, "operazioni")
    if "operation_snapshot" not in columns:
        connection.execute(
            text("ALTER TABLE operazioni ADD COLUMN operation_snapshot TEXT")
        )
        columns.add("operation_snapshot")

    if "giocatori_snapshot" not in columns:
        return

    rows = connection.execute(
        text(
            """
            SELECT id, fantasquadra_a_id, fantasquadra_b_id, tipo_operazione,
                   conguaglio, conguaglio_da_id, data, clausole,
                   giocatori_snapshot
            FROM operazioni
            WHERE operation_snapshot IS NULL
            """
        )
    ).mappings()

    for row in rows:
        connection.execute(
            text(
                """
                UPDATE operazioni
                SET operation_snapshot = :operation_snapshot
                WHERE id = :id
                """
            ),
            {"id": row["id"], "operation_snapshot": _legacy_payload(row)},
        )
