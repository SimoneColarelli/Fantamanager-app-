import unittest

from sqlalchemy import create_engine, text

from migration_runner import run_migrations


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
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
