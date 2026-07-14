from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import text


@dataclass(frozen=True)
class OutboxEvent:
    id: int
    event_type: str
    aggregate_type: str
    aggregate_id: Optional[int]
    payload: dict[str, Any]
    status: str
    retry_count: int
    last_error: Optional[str]


def enqueue_outbox_event(
    session_factory,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Optional[int],
    payload: dict[str, Any],
) -> int:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        result = session.execute(
            text(
                """
                INSERT INTO sync_outbox (
                    event_type, aggregate_type, aggregate_id, payload, status
                )
                VALUES (
                    :event_type, :aggregate_type, :aggregate_id, :payload, 'pending'
                )
                """
            ),
            {
                "event_type": event_type,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        )
        session.commit()
        return int(result.lastrowid)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def pending_outbox_events(session_factory, limit: int = 100) -> list[OutboxEvent]:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        rows = session.execute(
            text(
                """
                SELECT id, event_type, aggregate_type, aggregate_id, payload,
                       status, retry_count, last_error
                FROM sync_outbox
                WHERE status IN ('pending', 'failed')
                  AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP)
                ORDER BY id
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings()
        return [_row_to_event(row) for row in rows]
    finally:
        session.close()


def mark_outbox_synced(session_factory, event_id: int) -> None:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        session.execute(
            text(
                """
                UPDATE sync_outbox
                SET status = 'synced',
                    synced_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    last_error = NULL
                WHERE id = :event_id
                """
            ),
            {"event_id": event_id},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def mark_outbox_failed(
    session_factory,
    event_id: int,
    error: str,
    retry_delay_seconds: int = 60,
) -> None:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        next_attempt = None
        if retry_delay_seconds > 0:
            now = datetime.datetime.now(datetime.UTC)
            next_attempt = now + datetime.timedelta(seconds=retry_delay_seconds)
        session.execute(
            text(
                """
                UPDATE sync_outbox
                SET status = 'failed',
                    retry_count = retry_count + 1,
                    next_attempt_at = :next_attempt_at,
                    updated_at = CURRENT_TIMESTAMP,
                    last_error = :last_error
                WHERE id = :event_id
                """
            ),
            {
                "event_id": event_id,
                "next_attempt_at": next_attempt.isoformat() if next_attempt else None,
                "last_error": error,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _row_to_event(row) -> OutboxEvent:
    payload = json.loads(row["payload"] or "{}")
    return OutboxEvent(
        id=row["id"],
        event_type=row["event_type"],
        aggregate_type=row["aggregate_type"],
        aggregate_id=row["aggregate_id"],
        payload=payload,
        status=row["status"],
        retry_count=row["retry_count"],
        last_error=row["last_error"],
    )
