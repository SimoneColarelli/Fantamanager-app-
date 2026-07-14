from sqlalchemy import text


revision = "005_normalize_giocatore_team_refs"


def _columns(connection, table_name: str) -> set[str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


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


def upgrade(connection):
    if not _table_exists(connection, "giocatori") or not _table_exists(
        connection, "fantasquadre"
    ):
        return

    columns = _columns(connection, "giocatori")

    if "fantasquadra_id" not in columns:
        connection.execute(
            text(
                """
                ALTER TABLE giocatori
                ADD COLUMN fantasquadra_id INTEGER REFERENCES fantasquadre(id)
                """
            )
        )

    if "prestito_a_fantasquadra_id" not in columns:
        connection.execute(
            text(
                """
                ALTER TABLE giocatori
                ADD COLUMN prestito_a_fantasquadra_id INTEGER REFERENCES fantasquadre(id)
                """
            )
        )

    connection.execute(
        text(
            """
            UPDATE giocatori
            SET fantasquadra_id = (
                SELECT f.id
                FROM fantasquadre f
                WHERE f.nome = giocatori.squadra
                  AND COALESCE(f.deleted, 0) = 0
                ORDER BY f.id
                LIMIT 1
            )
            WHERE fantasquadra_id IS NULL
              AND squadra IS NOT NULL
              AND TRIM(squadra) <> ''
            """
        )
    )
    connection.execute(
        text(
            """
            UPDATE giocatori
            SET prestito_a_fantasquadra_id = (
                SELECT f.id
                FROM fantasquadre f
                WHERE f.nome = giocatori.in_prestito_a
                  AND COALESCE(f.deleted, 0) = 0
                ORDER BY f.id
                LIMIT 1
            )
            WHERE prestito_a_fantasquadra_id IS NULL
              AND in_prestito_a IS NOT NULL
              AND TRIM(in_prestito_a) <> ''
            """
        )
    )

    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_giocatori_fantasquadra_id "
            "ON giocatori(fantasquadra_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_giocatori_prestito_a_fantasquadra_id "
            "ON giocatori(prestito_a_fantasquadra_id)"
        )
    )
