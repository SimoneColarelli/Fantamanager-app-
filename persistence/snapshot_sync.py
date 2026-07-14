from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    select,
    text,
)
from sqlalchemy.engine import Engine

from models import Fantasquadra, Giocatore, Operazione, operazione_giocatori


FANTASQUADRE_TABLE = Fantasquadra.__table__
GIOCATORI_TABLE = Giocatore.__table__
OPERAZIONI_TABLE = Operazione.__table__
SYNC_METADATA = MetaData()
ENTITY_VERSIONS_TABLE = Table(
    "entity_versions",
    SYNC_METADATA,
    Column("entity_type", String, primary_key=True),
    Column("entity_id", Integer, primary_key=True),
    Column("local_version", Integer),
    Column("remote_version", Integer),
    Column("updated_at", DateTime),
    Column("synced_at", DateTime),
)
SEMANTIC_UNDO_LOG_TABLE = Table(
    "semantic_undo_log",
    SYNC_METADATA,
    Column("id", Integer, primary_key=True),
    Column("transaction_id", String),
    Column("operation_id", Integer),
    Column("action_type", String),
    Column("entity_type", String),
    Column("entity_id", Integer),
    Column("before_snapshot", Text),
    Column("after_snapshot", Text),
    Column("status", String),
    Column("created_at", DateTime),
    Column("undone_at", DateTime),
    Column("undo_error", Text),
    Column("operation_type", String),
    Column("inverse_action_type", String),
    Column("inverse_payload", Text),
)

INSERT_ORDER = (
    FANTASQUADRE_TABLE,
    GIOCATORI_TABLE,
    OPERAZIONI_TABLE,
    operazione_giocatori,
    ENTITY_VERSIONS_TABLE,
    SEMANTIC_UNDO_LOG_TABLE,
)

DELETE_ORDER = (
    SEMANTIC_UNDO_LOG_TABLE,
    ENTITY_VERSIONS_TABLE,
    operazione_giocatori,
    OPERAZIONI_TABLE,
    GIOCATORI_TABLE,
    FANTASQUADRE_TABLE,
)

IDENTITY_TABLES = (
    FANTASQUADRE_TABLE,
    GIOCATORI_TABLE,
    OPERAZIONI_TABLE,
    SEMANTIC_UNDO_LOG_TABLE,
)


@dataclass(frozen=True)
class SyncSnapshot:
    rows_by_table: dict[str, list[dict[str, Any]]]
    skipped_links: list[dict[str, Any]] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {table: len(rows) for table, rows in self.rows_by_table.items()}


@dataclass(frozen=True)
class SyncResult:
    status: str
    direction: str
    started_at: datetime.datetime
    finished_at: datetime.datetime
    counts: dict[str, int] = field(default_factory=dict)
    skipped_links: list[dict[str, Any]] = field(default_factory=list)
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class SnapshotSyncGateway:
    """Full-snapshot sync between local SQLite and the Supabase/Postgres schema."""

    def __init__(self, local_session_factory, remote_engine: Engine):
        self.local_session_factory = local_session_factory
        self.remote_engine = remote_engine

    def push_local_to_remote(self) -> SyncResult:
        started_at = datetime.datetime.now(datetime.UTC)
        snapshot = self._read_local_snapshot()

        with self.remote_engine.begin() as connection:
            self._write_snapshot(connection, snapshot)

        return SyncResult(
            status="ok",
            direction="push",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.UTC),
            counts=snapshot.counts,
            skipped_links=snapshot.skipped_links,
            message="Local SQLite snapshot pushed to Supabase.",
        )

    def pull_remote_to_local(self, local_engine: Engine) -> SyncResult:
        started_at = datetime.datetime.now(datetime.UTC)
        with self.remote_engine.connect() as connection:
            snapshot = self._read_snapshot_from_connection(connection)

        with local_engine.begin() as connection:
            if connection.dialect.name == "sqlite":
                connection.execute(text("PRAGMA foreign_keys=OFF"))
            self._write_snapshot(connection, snapshot)
            if connection.dialect.name == "sqlite":
                connection.execute(text("PRAGMA foreign_keys=ON"))

        return SyncResult(
            status="ok",
            direction="pull",
            started_at=started_at,
            finished_at=datetime.datetime.now(datetime.UTC),
            counts=snapshot.counts,
            skipped_links=snapshot.skipped_links,
            message="Supabase snapshot pulled into local SQLite.",
        )

    def _read_local_snapshot(self) -> SyncSnapshot:
        session = self.local_session_factory()
        session.info["skip_hybrid_sync"] = True
        try:
            return self._read_snapshot_from_connection(session.connection())
        finally:
            session.close()

    def _read_snapshot_from_connection(self, connection) -> SyncSnapshot:
        rows_by_table: dict[str, list[dict[str, Any]]] = {}

        for table in INSERT_ORDER:
            rows = connection.execute(select(table)).mappings().all()
            rows_by_table[table.name] = [dict(row) for row in rows]

        return self._filter_invalid_links(rows_by_table)

    def _filter_invalid_links(
        self,
        rows_by_table: dict[str, list[dict[str, Any]]],
    ) -> SyncSnapshot:
        operation_ids = {row["id"] for row in rows_by_table[OPERAZIONI_TABLE.name]}
        player_ids = {row["id"] for row in rows_by_table[GIOCATORI_TABLE.name]}

        valid_links: list[dict[str, Any]] = []
        skipped_links: list[dict[str, Any]] = []
        for row in rows_by_table[operazione_giocatori.name]:
            reasons = []
            if row["operazione_id"] not in operation_ids:
                reasons.append("missing operazione")
            if row["giocatore_id"] not in player_ids:
                reasons.append("missing giocatore")
            if reasons:
                skipped_links.append(
                    {
                        "operazione_id": row["operazione_id"],
                        "giocatore_id": row["giocatore_id"],
                        "reason": ", ".join(reasons),
                    }
                )
                continue
            valid_links.append(row)

        rows_by_table[operazione_giocatori.name] = valid_links
        return SyncSnapshot(rows_by_table=rows_by_table, skipped_links=skipped_links)

    def _write_snapshot(self, connection, snapshot: SyncSnapshot) -> None:
        for table in DELETE_ORDER:
            connection.execute(table.delete())

        for table in INSERT_ORDER:
            rows = snapshot.rows_by_table[table.name]
            if rows:
                connection.execute(table.insert(), rows)

        if connection.dialect.name == "postgresql":
            self._align_postgres_identity_sequences(connection)

    def _align_postgres_identity_sequences(self, connection) -> None:
        for table in IDENTITY_TABLES:
            connection.execute(
                text(
                    """
                    select setval(
                        pg_get_serial_sequence(:table_name, 'id'),
                        greatest(coalesce((select max(id) from {table_name}), 1), 1),
                        (select count(*) > 0 from {table_name})
                    )
                    """.format(table_name=f"public.{table.name}")
                ),
                {"table_name": f"public.{table.name}"},
            )
