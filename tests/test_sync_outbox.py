import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from migration_runner import run_migrations
from persistence.sync_outbox import (
    enqueue_outbox_event,
    mark_outbox_failed,
    mark_outbox_synced,
    pending_outbox_events,
)


class SyncOutboxTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        run_migrations(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)

    def tearDown(self):
        self.engine.dispose()

    def test_enqueue_mark_failed_and_synced(self):
        event_id = enqueue_outbox_event(
            self.Session,
            event_type="operazione_creata",
            aggregate_type="operazione",
            aggregate_id=10,
            payload={"tipo_operazione": "asta"},
        )

        pending = pending_outbox_events(self.Session)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].id, event_id)
        self.assertEqual(pending[0].payload, {"tipo_operazione": "asta"})

        mark_outbox_failed(
            self.Session,
            event_id=event_id,
            error="temporary network error",
            retry_delay_seconds=0,
        )
        failed = pending_outbox_events(self.Session)
        self.assertEqual(failed[0].status, "failed")
        self.assertEqual(failed[0].retry_count, 1)
        self.assertEqual(failed[0].last_error, "temporary network error")

        mark_outbox_synced(self.Session, event_id)
        self.assertEqual(pending_outbox_events(self.Session), [])


if __name__ == "__main__":
    unittest.main()
