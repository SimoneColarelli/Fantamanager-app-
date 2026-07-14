from sqlalchemy import text


revision = "007_integer_economic_values"


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


def _columns(connection, table_name: str) -> dict[str, str]:
    rows = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1]: (row[2] or "").upper() for row in rows}


def upgrade(connection):
    if not _table_exists(connection, "giocatori"):
        return

    columns = _columns(connection, "giocatori")
    if (
        columns.get("spesa") == "INTEGER"
        and columns.get("valore_svincolo") == "INTEGER"
    ):
        return

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    connection.execute(
        text(
            """
            CREATE TABLE giocatori_integer_values (
                id INTEGER PRIMARY KEY,
                nome VARCHAR NOT NULL,
                squadra VARCHAR,
                fantasquadra_id INTEGER REFERENCES fantasquadre(id),
                spesa INTEGER,
                data_acquisto DATE,
                fascia VARCHAR,
                quotazione INTEGER,
                dq INTEGER,
                valore_svincolo INTEGER,
                scadenza_contratto DATE,
                in_prestito_a VARCHAR,
                prestito_a_fantasquadra_id INTEGER REFERENCES fantasquadre(id),
                inizio_prestito DATE,
                fine_prestito DATE,
                convocato BOOLEAN,
                in_serie_a BOOLEAN,
                deleted BOOLEAN
            )
            """
        )
    )
    connection.execute(
        text(
            """
            INSERT INTO giocatori_integer_values (
                id, nome, squadra, fantasquadra_id, spesa, data_acquisto,
                fascia, quotazione, dq, valore_svincolo, scadenza_contratto,
                in_prestito_a, prestito_a_fantasquadra_id, inizio_prestito,
                fine_prestito, convocato, in_serie_a, deleted
            )
            SELECT
                id,
                nome,
                squadra,
                fantasquadra_id,
                CASE WHEN spesa IS NULL THEN NULL ELSE CAST(ROUND(spesa) AS INTEGER) END,
                data_acquisto,
                fascia,
                quotazione,
                dq,
                CASE
                    WHEN valore_svincolo IS NULL THEN NULL
                    ELSE CAST(ROUND(valore_svincolo) AS INTEGER)
                END,
                scadenza_contratto,
                in_prestito_a,
                prestito_a_fantasquadra_id,
                inizio_prestito,
                fine_prestito,
                convocato,
                in_serie_a,
                deleted
            FROM giocatori
            """
        )
    )
    connection.execute(text("DROP TABLE giocatori"))
    connection.execute(text("ALTER TABLE giocatori_integer_values RENAME TO giocatori"))
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
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS idx_giocatori_squadra ON giocatori(squadra)")
    )
    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_giocatori_in_prestito_a "
            "ON giocatori(in_prestito_a)"
        )
    )
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS idx_giocatori_deleted ON giocatori(deleted)")
    )
    connection.execute(text("PRAGMA foreign_keys=ON"))
