from sqlalchemy import text


revision = "009_operation_season_context"


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


def upgrade(connection):
    if not _table_exists(connection, "operazioni"):
        return

    columns = _columns(connection, "operazioni")
    if "stagione_id" not in columns:
        connection.execute(
            text("ALTER TABLE operazioni ADD COLUMN stagione_id INTEGER REFERENCES stagioni(id)")
        )
    if "fase_stagione" not in columns:
        connection.execute(text("ALTER TABLE operazioni ADD COLUMN fase_stagione VARCHAR"))
    if "periodo_regolamento" not in columns:
        connection.execute(
            text("ALTER TABLE operazioni ADD COLUMN periodo_regolamento VARCHAR")
        )
    if "mese_regolamento" not in columns:
        connection.execute(
            text("ALTER TABLE operazioni ADD COLUMN mese_regolamento VARCHAR")
        )

    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_operazioni_stagione_id
            ON operazioni(stagione_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_operazioni_fase_stagione
            ON operazioni(fase_stagione)
            """
        )
    )
