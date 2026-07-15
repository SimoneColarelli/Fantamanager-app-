import importlib
import unittest

from sqlalchemy import create_engine, text

from migration_runner import run_migrations

team_refs_migration = importlib.import_module(
    "migrations.005_normalize_giocatore_team_refs"
)
operation_snapshot_migration = importlib.import_module(
    "migrations.006_operation_snapshot"
)
integer_values_migration = importlib.import_module(
    "migrations.007_integer_economic_values"
)


class MigrationRunnerTests(unittest.TestCase):
    def test_run_migrations_records_revisions_once(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            first = run_migrations(engine)
            second = run_migrations(engine)

            with engine.connect() as connection:
                rows = connection.execute(
                    text("SELECT revision FROM schema_migrations ORDER BY revision")
                ).fetchall()
                sync_state_exists = connection.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM sqlite_master
                        WHERE type = 'table' AND name = 'sync_state'
                        """
                    )
                ).scalar()
                reliability_tables = connection.execute(
                    text(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                          AND name IN (
                              'sync_outbox',
                              'entity_versions',
                              'semantic_undo_log'
                          )
                        ORDER BY name
                        """
                    )
                ).fetchall()
                semantic_columns = connection.execute(
                    text("PRAGMA table_info(semantic_undo_log)")
                ).fetchall()

            expected_revisions = [
                "001_baseline",
                "002_sync_state",
                "003_reliability_foundations",
                "004_semantic_undo_inverse_metadata",
                "005_normalize_giocatore_team_refs",
                "006_operation_snapshot",
                "007_integer_economic_values",
                "008_stagioni",
            ]
            self.assertEqual(first, expected_revisions)
            self.assertEqual(second, [])
            self.assertEqual([row[0] for row in rows], expected_revisions)
            self.assertEqual(sync_state_exists, 1)
            self.assertEqual(
                [row[0] for row in reliability_tables],
                ["entity_versions", "semantic_undo_log", "sync_outbox"],
            )
            self.assertIn("operation_type", {row[1] for row in semantic_columns})
            self.assertIn("inverse_action_type", {row[1] for row in semantic_columns})
            self.assertIn("inverse_payload", {row[1] for row in semantic_columns})

            with engine.connect() as connection:
                stagione_tables = connection.execute(
                    text(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                          AND name IN (
                              'stagioni',
                              'stagione_fasi',
                              'stagione_files',
                              'stagione_step_log'
                          )
                        ORDER BY name
                        """
                    )
                ).fetchall()
            self.assertEqual(
                [row[0] for row in stagione_tables],
                [
                    "stagione_fasi",
                    "stagione_files",
                    "stagione_step_log",
                    "stagioni",
                ],
            )
        finally:
            engine.dispose()

    def test_operation_snapshot_migration_backfills_legacy_player_snapshot(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE operazioni (
                            id INTEGER PRIMARY KEY,
                            fantasquadra_a_id INTEGER NOT NULL,
                            fantasquadra_b_id INTEGER,
                            tipo_operazione VARCHAR NOT NULL,
                            conguaglio INTEGER,
                            conguaglio_da_id INTEGER,
                            data DATE,
                            clausole VARCHAR,
                            giocatori_snapshot TEXT
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO operazioni (
                            id, fantasquadra_a_id, fantasquadra_b_id,
                            tipo_operazione, conguaglio, conguaglio_da_id,
                            data, clausole, giocatori_snapshot
                        )
                        VALUES (
                            1, 10, NULL, 'svincolo', 0, NULL,
                            '2026-08-01', '',
                            '[{"nome": "Released", "valore_svincolo": 75}]'
                        )
                        """
                    )
                )

                operation_snapshot_migration.upgrade(connection)

                row = connection.execute(
                    text(
                        """
                        SELECT operation_snapshot
                        FROM operazioni
                        WHERE id = 1
                        """
                    )
                ).scalar()

            self.assertIn("legacy_migration", row)
            self.assertIn("Released", row)
        finally:
            engine.dispose()

    def test_team_reference_migration_backfills_fk_columns(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE fantasquadre (
                            id INTEGER PRIMARY KEY,
                            nome VARCHAR NOT NULL,
                            deleted BOOLEAN DEFAULT 0
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE giocatori (
                            id INTEGER PRIMARY KEY,
                            nome VARCHAR NOT NULL,
                            squadra VARCHAR,
                            in_prestito_a VARCHAR
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO fantasquadre (id, nome, deleted)
                        VALUES (1, 'Owner', 0), (2, 'Loan Team', 0)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO giocatori (id, nome, squadra, in_prestito_a)
                        VALUES (10, 'Player', 'Owner', 'Loan Team')
                        """
                    )
                )

                team_refs_migration.upgrade(connection)

                columns = {
                    row[1]
                    for row in connection.execute(
                        text("PRAGMA table_info(giocatori)")
                    ).fetchall()
                }
                row = connection.execute(
                    text(
                        """
                        SELECT squadra, fantasquadra_id,
                               in_prestito_a, prestito_a_fantasquadra_id
                        FROM giocatori
                        WHERE id = 10
                        """
                    )
                ).fetchone()

            self.assertIn("fantasquadra_id", columns)
            self.assertIn("prestito_a_fantasquadra_id", columns)
            self.assertEqual(row[0], "Owner")
            self.assertEqual(row[1], 1)
            self.assertEqual(row[2], "Loan Team")
            self.assertEqual(row[3], 2)
        finally:
            engine.dispose()

    def test_integer_values_migration_rounds_legacy_float_columns(self):
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE fantasquadre (
                            id INTEGER PRIMARY KEY,
                            nome VARCHAR NOT NULL
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE giocatori (
                            id INTEGER PRIMARY KEY,
                            nome VARCHAR NOT NULL,
                            squadra VARCHAR,
                            fantasquadra_id INTEGER,
                            spesa FLOAT,
                            data_acquisto DATE,
                            fascia VARCHAR,
                            quotazione INTEGER,
                            dq INTEGER,
                            valore_svincolo FLOAT,
                            scadenza_contratto DATE,
                            in_prestito_a VARCHAR,
                            prestito_a_fantasquadra_id INTEGER,
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
                        INSERT INTO giocatori (
                            id, nome, spesa, valore_svincolo, convocato,
                            in_serie_a, deleted
                        )
                        VALUES (1, 'Rounded', 84.19, 84.51, 1, 1, 0)
                        """
                    )
                )

                integer_values_migration.upgrade(connection)

                columns = {
                    row[1]: row[2].upper()
                    for row in connection.execute(
                        text("PRAGMA table_info(giocatori)")
                    ).fetchall()
                }
                row = connection.execute(
                    text("SELECT spesa, valore_svincolo FROM giocatori WHERE id = 1")
                ).fetchone()

            self.assertEqual(columns["spesa"], "INTEGER")
            self.assertEqual(columns["valore_svincolo"], "INTEGER")
            self.assertEqual(row[0], 84)
            self.assertEqual(row[1], 85)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
