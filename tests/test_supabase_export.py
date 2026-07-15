import sqlite3
import unittest

from scripts.export_sqlite_to_supabase_seed import build_seed, validate_schema


class SupabaseSeedExporterTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def tearDown(self):
        self.conn.close()

    def _create_schema(self):
        self.conn.executescript(
            """
            create table stagioni (
                id integer primary key,
                codice varchar not null,
                anno_inizio integer not null,
                anno_fine integer not null,
                data_inizio date not null,
                data_fine date,
                stato varchar not null,
                fase_corrente varchar,
                storage_path text not null,
                created_at timestamp,
                updated_at timestamp,
                deleted boolean
            );

            create table stagione_fasi (
                id integer primary key,
                stagione_id integer not null,
                codice_fase varchar not null,
                nome varchar not null,
                data_inizio date,
                data_fine date,
                stato varchar not null,
                asta_data_inizio date,
                asta_data_fine date,
                created_at timestamp,
                updated_at timestamp
            );

            create table stagione_files (
                id integer primary key,
                stagione_id integer not null,
                fase_id integer,
                tipo_file varchar not null,
                nome_logico varchar not null,
                path text not null,
                created_at timestamp,
                note text
            );

            create table stagione_step_log (
                id integer primary key,
                stagione_id integer not null,
                fase_id integer,
                step_key varchar not null,
                status varchar not null,
                started_at timestamp,
                completed_at timestamp,
                error_message text,
                metadata_json text
            );

            create table fantasquadre (
                id integer primary key,
                nome varchar not null,
                fm integer not null,
                campionati integer,
                coppe integer,
                supercoppe integer,
                deleted boolean
            );

            create table giocatori (
                id integer primary key,
                nome varchar not null,
                squadra varchar,
                fantasquadra_id integer,
                spesa integer,
                data_acquisto date,
                fascia varchar,
                quotazione integer,
                dq integer,
                valore_svincolo integer,
                scadenza_contratto date,
                in_prestito_a varchar,
                prestito_a_fantasquadra_id integer,
                inizio_prestito date,
                fine_prestito date,
                convocato boolean,
                in_serie_a boolean,
                deleted boolean
            );

            create table operazioni (
                id integer primary key,
                fantasquadra_a_id integer not null,
                fantasquadra_b_id integer,
                tipo_operazione varchar not null,
                conguaglio integer,
                conguaglio_da_id integer,
                data date,
                clausole varchar,
                operation_snapshot text
            );

            create table operazione_giocatori (
                operazione_id integer not null,
                giocatore_id integer not null,
                primary key (operazione_id, giocatore_id)
            );

            create table entity_versions (
                entity_type varchar not null,
                entity_id integer not null,
                local_version integer not null,
                remote_version integer not null,
                updated_at timestamp,
                synced_at timestamp,
                primary key (entity_type, entity_id)
            );

            create table semantic_undo_log (
                id integer primary key,
                transaction_id varchar not null,
                operation_id integer,
                action_type varchar not null,
                entity_type varchar not null,
                entity_id integer,
                before_snapshot text,
                after_snapshot text,
                status varchar not null,
                created_at timestamp,
                undone_at timestamp,
                undo_error text,
                operation_type varchar,
                inverse_action_type varchar,
                inverse_payload text
            );
            """
        )

    def test_seed_skips_orphan_operation_players(self):
        self.conn.execute(
            """
            insert into stagioni
                (
                    id, codice, anno_inizio, anno_fine, data_inizio,
                    data_fine, stato, fase_corrente, storage_path,
                    created_at, updated_at, deleted
                )
            values
                (
                    1, '2026/2027', 2026, 2027, '2026-08-01',
                    null, 'attiva', 'fase_1_estiva', 'Stagioni/2026-2027',
                    '2026-07-15 12:00:00', '2026-07-15 12:00:00', 0
                )
            """
        )
        self.conn.execute(
            """
            insert into stagione_fasi
                (
                    id, stagione_id, codice_fase, nome, data_inizio,
                    data_fine, stato, asta_data_inizio, asta_data_fine,
                    created_at, updated_at
                )
            values
                (
                    2, 1, 'fase_1_estiva',
                    'Inizio stagione - sessione mercato estiva',
                    '2026-08-01', null, 'aperta', null, null,
                    '2026-07-15 12:00:00', '2026-07-15 12:00:00'
                )
            """
        )
        self.conn.execute(
            """
            insert into stagione_files
                (id, stagione_id, fase_id, tipo_file, nome_logico, path, created_at, note)
            values
                (
                    3, 1, 2, 'quotazioni_iniziali',
                    'Quotazioni iniziali stagione 2026/2027',
                    'Stagioni/2026-2027/01_fase_estiva/quotazioni/file.xlsx',
                    '2026-07-15 12:00:00', null
                )
            """
        )
        self.conn.execute(
            """
            insert into stagione_step_log
                (
                    id, stagione_id, fase_id, step_key, status,
                    started_at, completed_at, error_message, metadata_json
                )
            values
                (
                    4, 1, 2, 'crea_stagione', 'completed',
                    '2026-07-15 12:00:00', '2026-07-15 12:00:01',
                    null, '{"codice": "2026/2027"}'
                )
            """
        )
        self.conn.execute(
            """
            insert into fantasquadre
                (id, nome, fm, campionati, coppe, supercoppe, deleted)
            values
                (1, 'Team A', 100, 0, 0, 0, 0)
            """
        )
        self.conn.execute(
            """
            insert into giocatori
                (
                    id, nome, squadra, spesa, data_acquisto, fascia, quotazione,
                    fantasquadra_id, dq, valore_svincolo, scadenza_contratto,
                    in_prestito_a, prestito_a_fantasquadra_id, inizio_prestito,
                    fine_prestito, convocato, in_serie_a, deleted
                )
            values
                (
                    10, 'Player A', 'Team A', 1.0, '2026-01-01', '1', 10,
                    1, 0, 1.0, '2028-07-01', null, null, null, null, 1, 1, 0
                )
            """
        )
        self.conn.execute(
            """
            insert into operazioni
                (
                    id, fantasquadra_a_id, fantasquadra_b_id, tipo_operazione,
                    conguaglio, conguaglio_da_id, data, clausole,
                    operation_snapshot
                )
            values
                (
                    20, 1, null, 'asta', 0, null, '2026-07-14', null,
                    '{"schema_version": 1, "tipo_operazione": "asta"}'
                )
            """
        )
        self.conn.execute(
            "insert into operazione_giocatori values (20, 10)"
        )
        self.conn.execute(
            "insert into operazione_giocatori values (99, 10)"
        )
        self.conn.execute(
            """
            insert into entity_versions
                (entity_type, entity_id, local_version, remote_version, updated_at, synced_at)
            values
                ('giocatore', 10, 2, 1, '2026-07-14 12:00:00', null)
            """
        )
        self.conn.execute(
            """
            insert into semantic_undo_log
                (
                    id, transaction_id, operation_id, action_type, entity_type,
                    entity_id, before_snapshot, after_snapshot, status,
                    created_at, undone_at, undo_error, operation_type,
                    inverse_action_type, inverse_payload
                )
            values
                (
                    30, 'tx-1', 20, 'asta', 'giocatore',
                    10, null, '{"id": 10}', 'active',
                    '2026-07-14 12:00:00', null, null, 'asta',
                    'undo_asta', '{"operation_id": 20}'
                )
            """
        )

        validate_schema(self.conn)
        seed_sql, counts, skipped_rows = build_seed(self.conn, truncate=False)

        self.assertEqual(counts["operazione_giocatori"], 1)
        self.assertEqual(counts["stagioni"], 1)
        self.assertEqual(counts["stagione_fasi"], 1)
        self.assertEqual(counts["stagione_files"], 1)
        self.assertEqual(counts["stagione_step_log"], 1)
        self.assertEqual(counts["entity_versions"], 1)
        self.assertEqual(counts["semantic_undo_log"], 1)
        self.assertEqual(skipped_rows, [(99, 10, "missing operazione")])
        self.assertIn(
            "insert into public.operazione_giocatori "
            "(operazione_id, giocatore_id) values (20, 10);",
            seed_sql,
        )
        self.assertIn(
            "insert into public.entity_versions "
            "(entity_type, entity_id, local_version, remote_version, updated_at, synced_at) "
            "values ('giocatore', 10, 2, 1, '2026-07-14 12:00:00', null);",
            seed_sql,
        )
        self.assertIn("insert into public.semantic_undo_log", seed_sql)
        self.assertIn("insert into public.stagioni", seed_sql)
        self.assertIn("insert into public.stagione_fasi", seed_sql)
        self.assertIn("insert into public.stagione_files", seed_sql)
        self.assertIn("insert into public.stagione_step_log", seed_sql)
        self.assertNotIn(
            "insert into public.operazione_giocatori "
            "(operazione_id, giocatore_id) values (99, 10);",
            seed_sql,
        )


if __name__ == "__main__":
    unittest.main()
