from sqlalchemy import text


revision = "010_june_contract_expiry"


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


def _move_july_first_dates(connection, table_name: str, column_name: str) -> None:
    if not _table_exists(connection, table_name):
        return
    if column_name not in _columns(connection, table_name):
        return
    connection.execute(
        text(
            f"""
            UPDATE {table_name}
            SET {column_name} = substr({column_name}, 1, 4) || '-06-30'
            WHERE {column_name} LIKE '____-07-01'
            """
        )
    )


def _replace_july_first_text(connection, table_name: str, column_name: str) -> None:
    if not _table_exists(connection, table_name):
        return
    if column_name not in _columns(connection, table_name):
        return
    connection.execute(
        text(
            f"""
            UPDATE {table_name}
            SET {column_name} = replace({column_name}, '-07-01', '-06-30')
            WHERE {column_name} LIKE '%-07-01%'
            """
        )
    )


def upgrade(connection):
    _move_july_first_dates(connection, "giocatori", "scadenza_contratto")
    _move_july_first_dates(connection, "giocatori", "fine_prestito")

    _replace_july_first_text(connection, "operazioni", "operation_snapshot")
    for column_name in ("before_snapshot", "after_snapshot", "inverse_payload"):
        _replace_july_first_text(connection, "semantic_undo_log", column_name)
