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

            self.assertEqual(first, ["001_baseline", "002_sync_state"])
            self.assertEqual(second, [])
            self.assertEqual([row[0] for row in rows], ["001_baseline", "002_sync_state"])
            self.assertEqual(sync_state_exists, 1)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
