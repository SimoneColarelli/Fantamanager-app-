"""Reliability foundations: semantic undo audit and sync retry state."""

from sqlalchemy import text


revision = "003_reliability_foundations"


def upgrade(connection):
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sync_outbox (
                id INTEGER PRIMARY KEY,
                event_type VARCHAR NOT NULL,
                aggregate_type VARCHAR NOT NULL,
                aggregate_id INTEGER,
                payload TEXT NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                retry_count INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TIMESTAMP,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_outbox_status_next_attempt
            ON sync_outbox(status, next_attempt_at)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_sync_outbox_aggregate
            ON sync_outbox(aggregate_type, aggregate_id)
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS entity_versions (
                entity_type VARCHAR NOT NULL,
                entity_id INTEGER NOT NULL,
                local_version INTEGER NOT NULL DEFAULT 0,
                remote_version INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP,
                PRIMARY KEY (entity_type, entity_id)
            )
            """
        )
    )

    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS semantic_undo_log (
                id INTEGER PRIMARY KEY,
                transaction_id VARCHAR NOT NULL,
                operation_id INTEGER,
                action_type VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id INTEGER,
                before_snapshot TEXT,
                after_snapshot TEXT,
                status VARCHAR NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                undone_at TIMESTAMP,
                undo_error TEXT
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_semantic_undo_log_transaction
            ON semantic_undo_log(transaction_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_semantic_undo_log_operation
            ON semantic_undo_log(operation_id)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_semantic_undo_log_status
            ON semantic_undo_log(status)
            """
        )
    )
