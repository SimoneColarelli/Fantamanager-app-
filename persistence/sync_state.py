from __future__ import annotations

import datetime
import json
from typing import Any

from sqlalchemy import text


SYNC_STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sync_state (
    key VARCHAR PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_sync_state_table(connection) -> None:
    connection.execute(text(SYNC_STATE_TABLE_SQL))


def _serialize(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if value is None:
        return ""
    return str(value)


def write_sync_state(session_factory, values: dict[str, Any]) -> None:
    """Best-effort local sync metadata write.

    The session is marked so the hybrid listener does not recursively sync the
    metadata commit itself.
    """
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        ensure_sync_state_table(session.connection())
        now = datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()
        dialect_name = session.get_bind().dialect.name

        for key, value in values.items():
            params = {"key": key, "value": _serialize(value), "updated_at": now}
            if dialect_name == "sqlite":
                statement = text(
                    """
                    INSERT OR REPLACE INTO sync_state (key, value, updated_at)
                    VALUES (:key, :value, :updated_at)
                    """
                )
            else:
                statement = text(
                    """
                    INSERT INTO sync_state (key, value, updated_at)
                    VALUES (:key, :value, :updated_at)
                    ON CONFLICT (key)
                    DO UPDATE SET value = EXCLUDED.value,
                                  updated_at = EXCLUDED.updated_at
                    """
                )
            session.execute(statement, params)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def read_sync_state(session_factory) -> dict[str, str]:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        ensure_sync_state_table(session.connection())
        rows = session.execute(text("SELECT key, value FROM sync_state")).fetchall()
        return {row[0]: row[1] for row in rows}
    finally:
        session.close()
