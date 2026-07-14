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
                spesa float,
                data_acquisto date,
                fascia varchar,
                quotazione integer,
                dq integer,
                valore_svincolo float,
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
                giocatori_snapshot text
            );

            create table operazione_giocatori (
                operazione_id integer not null,
                giocatore_id integer not null,
                primary key (operazione_id, giocatore_id)
            );
            """
        )

    def test_seed_skips_orphan_operation_players(self):
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
                    giocatori_snapshot
                )
            values
                (20, 1, null, 'asta', 0, null, '2026-07-14', null, null)
            """
        )
        self.conn.execute(
            "insert into operazione_giocatori values (20, 10)"
        )
        self.conn.execute(
            "insert into operazione_giocatori values (99, 10)"
        )

        validate_schema(self.conn)
        seed_sql, counts, skipped_rows = build_seed(self.conn, truncate=False)

        self.assertEqual(counts["operazione_giocatori"], 1)
        self.assertEqual(skipped_rows, [(99, 10, "missing operazione")])
        self.assertIn(
            "insert into public.operazione_giocatori "
            "(operazione_id, giocatore_id) values (20, 10);",
            seed_sql,
        )
        self.assertNotIn(
            "insert into public.operazione_giocatori "
            "(operazione_id, giocatore_id) values (99, 10);",
            seed_sql,
        )


if __name__ == "__main__":
    unittest.main()
