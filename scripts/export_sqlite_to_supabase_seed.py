from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from pathlib import Path
from typing import Iterable


TABLE_COLUMNS = {
    "stagioni": (
        "id",
        "codice",
        "anno_inizio",
        "anno_fine",
        "data_inizio",
        "data_fine",
        "stato",
        "fase_corrente",
        "storage_path",
        "created_at",
        "updated_at",
        "deleted",
    ),
    "stagione_fasi": (
        "id",
        "stagione_id",
        "codice_fase",
        "nome",
        "data_inizio",
        "data_fine",
        "stato",
        "asta_data_inizio",
        "asta_data_fine",
        "created_at",
        "updated_at",
    ),
    "stagione_files": (
        "id",
        "stagione_id",
        "fase_id",
        "tipo_file",
        "nome_logico",
        "path",
        "created_at",
        "note",
    ),
    "stagione_step_log": (
        "id",
        "stagione_id",
        "fase_id",
        "step_key",
        "status",
        "started_at",
        "completed_at",
        "error_message",
        "metadata_json",
    ),
    "fantasquadre": (
        "id",
        "nome",
        "fm",
        "campionati",
        "coppe",
        "supercoppe",
        "deleted",
    ),
    "giocatori": (
        "id",
        "nome",
        "squadra",
        "fantasquadra_id",
        "spesa",
        "data_acquisto",
        "fascia",
        "quotazione",
        "dq",
        "valore_svincolo",
        "scadenza_contratto",
        "in_prestito_a",
        "prestito_a_fantasquadra_id",
        "inizio_prestito",
        "fine_prestito",
        "convocato",
        "in_serie_a",
        "deleted",
    ),
    "operazioni": (
        "id",
        "fantasquadra_a_id",
        "fantasquadra_b_id",
        "tipo_operazione",
        "conguaglio",
        "conguaglio_da_id",
        "data",
        "clausole",
        "stagione_id",
        "fase_stagione",
        "periodo_regolamento",
        "mese_regolamento",
        "operation_snapshot",
    ),
    "operazione_giocatori": (
        "operazione_id",
        "giocatore_id",
    ),
    "entity_versions": (
        "entity_type",
        "entity_id",
        "local_version",
        "remote_version",
        "updated_at",
        "synced_at",
    ),
    "semantic_undo_log": (
        "id",
        "transaction_id",
        "operation_id",
        "action_type",
        "entity_type",
        "entity_id",
        "before_snapshot",
        "after_snapshot",
        "status",
        "created_at",
        "undone_at",
        "undo_error",
        "operation_type",
        "inverse_action_type",
        "inverse_payload",
    ),
}

BOOLEAN_COLUMNS = {
    ("stagioni", "deleted"),
    ("fantasquadre", "deleted"),
    ("giocatori", "convocato"),
    ("giocatori", "in_serie_a"),
    ("giocatori", "deleted"),
}

NUMERIC_COLUMNS = {
    ("stagioni", "id"),
    ("stagioni", "anno_inizio"),
    ("stagioni", "anno_fine"),
    ("stagione_fasi", "id"),
    ("stagione_fasi", "stagione_id"),
    ("stagione_files", "id"),
    ("stagione_files", "stagione_id"),
    ("stagione_files", "fase_id"),
    ("stagione_step_log", "id"),
    ("stagione_step_log", "stagione_id"),
    ("stagione_step_log", "fase_id"),
    ("fantasquadre", "id"),
    ("fantasquadre", "fm"),
    ("fantasquadre", "campionati"),
    ("fantasquadre", "coppe"),
    ("fantasquadre", "supercoppe"),
    ("giocatori", "id"),
    ("giocatori", "fantasquadra_id"),
    ("giocatori", "spesa"),
    ("giocatori", "quotazione"),
    ("giocatori", "dq"),
    ("giocatori", "valore_svincolo"),
    ("giocatori", "prestito_a_fantasquadra_id"),
    ("operazioni", "id"),
    ("operazioni", "fantasquadra_a_id"),
    ("operazioni", "fantasquadra_b_id"),
    ("operazioni", "conguaglio"),
    ("operazioni", "conguaglio_da_id"),
    ("operazioni", "stagione_id"),
    ("operazione_giocatori", "operazione_id"),
    ("operazione_giocatori", "giocatore_id"),
    ("entity_versions", "entity_id"),
    ("entity_versions", "local_version"),
    ("entity_versions", "remote_version"),
    ("semantic_undo_log", "id"),
    ("semantic_undo_log", "operation_id"),
    ("semantic_undo_log", "entity_id"),
}

SEQUENCE_TABLES = (
    "stagioni",
    "stagione_fasi",
    "stagione_files",
    "stagione_step_log",
    "fantasquadre",
    "giocatori",
    "operazioni",
    "semantic_undo_log",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the local SQLite data as a Supabase/Postgres seed.sql file."
    )
    parser.add_argument("--db", default="fantamanager.db", help="SQLite database path.")
    parser.add_argument(
        "--out",
        default="supabase/seed.sql",
        help="Destination SQL seed file.",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate target tables before inserting data.",
    )
    return parser.parse_args()


def quote_text(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def bool_literal(value: object, table: str, column: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return "true" if value else "false"

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y"}:
        return "true"
    if normalized in {"0", "false", "f", "no", "n"}:
        return "false"

    raise ValueError(f"Invalid boolean value for {table}.{column}: {value!r}")


def numeric_literal(value: object, table: str, column: str) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Invalid numeric value for {table}.{column}: {value!r}")
        return repr(value)

    if isinstance(value, int):
        return str(value)

    text = str(value).strip()
    if not text:
        raise ValueError(f"Empty numeric value for {table}.{column}")
    return text


def sql_literal(table: str, column: str, value: object) -> str:
    if value is None:
        return "null"
    if (table, column) in BOOLEAN_COLUMNS:
        return bool_literal(value, table, column)
    if (table, column) in NUMERIC_COLUMNS:
        return numeric_literal(value, table, column)
    return quote_text(value)


def fetch_rows(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    columns = TABLE_COLUMNS[table]
    column_sql = ", ".join(columns)
    if table == "operazione_giocatori":
        order_sql = "operazione_id, giocatore_id"
    elif table == "entity_versions":
        order_sql = "entity_type, entity_id"
    else:
        order_sql = "id"
    return list(conn.execute(f"select {column_sql} from {table} order by {order_sql}"))


def validate_schema(conn: sqlite3.Connection) -> None:
    for table, expected_columns in TABLE_COLUMNS.items():
        actual_columns = {
            row["name"] for row in conn.execute(f"pragma table_info({table})")
        }
        missing_columns = [col for col in expected_columns if col not in actual_columns]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise RuntimeError(f"Missing columns in SQLite table {table}: {missing}")


def filter_valid_operation_players(
    conn: sqlite3.Connection,
    rows: Iterable[sqlite3.Row],
) -> tuple[list[sqlite3.Row], list[tuple[int, int, str]]]:
    operation_ids = {row["id"] for row in conn.execute("select id from operazioni")}
    player_ids = {row["id"] for row in conn.execute("select id from giocatori")}

    valid_rows: list[sqlite3.Row] = []
    skipped_rows: list[tuple[int, int, str]] = []
    for row in rows:
        operation_id = row["operazione_id"]
        player_id = row["giocatore_id"]
        reasons = []
        if operation_id not in operation_ids:
            reasons.append("missing operazione")
        if player_id not in player_ids:
            reasons.append("missing giocatore")
        if reasons:
            skipped_rows.append((operation_id, player_id, ", ".join(reasons)))
            continue
        valid_rows.append(row)

    return valid_rows, skipped_rows


def insert_statement(table: str, row: sqlite3.Row) -> str:
    columns = TABLE_COLUMNS[table]
    columns_sql = ", ".join(columns)
    values_sql = ", ".join(sql_literal(table, col, row[col]) for col in columns)
    return f"insert into public.{table} ({columns_sql}) values ({values_sql});"


def sequence_statement(table: str) -> str:
    return (
        "select setval("
        f"pg_get_serial_sequence('public.{table}', 'id'), "
        f"greatest(coalesce((select max(id) from public.{table}), 1), 1), "
        f"(select count(*) > 0 from public.{table})"
        ");"
    )


def build_seed(
    conn: sqlite3.Connection,
    truncate: bool,
) -> tuple[str, dict[str, int], list[tuple[int, int, str]]]:
    rows_by_table = {table: fetch_rows(conn, table) for table in TABLE_COLUMNS}
    valid_operation_players, skipped_rows = filter_valid_operation_players(
        conn,
        rows_by_table["operazione_giocatori"],
    )
    rows_by_table["operazione_giocatori"] = valid_operation_players

    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    lines = [
        "-- Generated from fantamanager.db by scripts/export_sqlite_to_supabase_seed.py.",
        "-- Re-run the exporter whenever the versioned SQLite data changes.",
        "begin;",
        "",
    ]

    if truncate:
        lines.extend(
            [
                "truncate table",
                "    public.semantic_undo_log,",
                "    public.entity_versions,",
                "    public.operazione_giocatori,",
                "    public.operazioni,",
                "    public.giocatori,",
                "    public.fantasquadre,",
                "    public.stagione_step_log,",
                "    public.stagione_files,",
                "    public.stagione_fasi,",
                "    public.stagioni",
                "restart identity cascade;",
                "",
            ]
        )

    if skipped_rows:
        lines.append("-- Skipped invalid operazione_giocatori rows:")
        for operation_id, player_id, reason in skipped_rows:
            lines.append(
                f"-- operazione_id={operation_id}, giocatore_id={player_id}: {reason}"
            )
        lines.append("")

    for table in TABLE_COLUMNS:
        lines.append(f"-- {table}: {counts[table]} rows")
        for row in rows_by_table[table]:
            lines.append(insert_statement(table, row))
        lines.append("")

    lines.append("-- Align identity sequences after explicit ID inserts.")
    for table in SEQUENCE_TABLES:
        lines.append(sequence_statement(table))
    lines.extend(["", "commit;", ""])

    return "\n".join(lines), counts, skipped_rows


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)

    if not db_path.exists():
        print(f"SQLite database not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        validate_schema(conn)
        seed_sql, counts, skipped_rows = build_seed(conn, truncate=not args.no_truncate)
    finally:
        conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(seed_sql, encoding="utf-8", newline="\n")

    print(f"Wrote {out_path}", file=sys.stderr)
    for table, count in counts.items():
        print(f"{table}: {count} rows", file=sys.stderr)
    if skipped_rows:
        print(
            f"Skipped {len(skipped_rows)} invalid operazione_giocatori rows",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
