"""Local sync state for hybrid SQLite/Supabase persistence."""

from sqlalchemy import text


revision = "002_sync_state"


def upgrade(connection):
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                key VARCHAR PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
