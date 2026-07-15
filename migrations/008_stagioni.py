from sqlalchemy import text


revision = "008_stagioni"


def upgrade(connection):
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stagioni (
                id INTEGER PRIMARY KEY,
                codice VARCHAR NOT NULL UNIQUE,
                anno_inizio INTEGER NOT NULL,
                anno_fine INTEGER NOT NULL,
                data_inizio DATE NOT NULL,
                data_fine DATE,
                stato VARCHAR NOT NULL DEFAULT 'attiva',
                fase_corrente VARCHAR,
                storage_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deleted BOOLEAN DEFAULT 0
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stagione_fasi (
                id INTEGER PRIMARY KEY,
                stagione_id INTEGER NOT NULL REFERENCES stagioni(id),
                codice_fase VARCHAR NOT NULL,
                nome VARCHAR NOT NULL,
                data_inizio DATE,
                data_fine DATE,
                stato VARCHAR NOT NULL DEFAULT 'pianificata',
                asta_data_inizio DATE,
                asta_data_fine DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (stagione_id, codice_fase)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stagione_files (
                id INTEGER PRIMARY KEY,
                stagione_id INTEGER NOT NULL REFERENCES stagioni(id),
                fase_id INTEGER REFERENCES stagione_fasi(id),
                tipo_file VARCHAR NOT NULL,
                nome_logico VARCHAR NOT NULL,
                path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS stagione_step_log (
                id INTEGER PRIMARY KEY,
                stagione_id INTEGER NOT NULL REFERENCES stagioni(id),
                fase_id INTEGER REFERENCES stagione_fasi(id),
                step_key VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                metadata_json TEXT
            )
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_stagioni_single_active
            ON stagioni(stato)
            WHERE stato = 'attiva' AND COALESCE(deleted, 0) = 0
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_stagione_fasi_stagione_id
            ON stagione_fasi(stagione_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_stagione_files_stagione_id
            ON stagione_files(stagione_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_stagione_files_fase_id
            ON stagione_files(fase_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_stagione_step_log_stagione_id
            ON stagione_step_log(stagione_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_stagione_step_log_fase_id
            ON stagione_step_log(fase_id)
            """
        )
    )
