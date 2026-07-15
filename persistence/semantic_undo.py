from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import inspect, text

from models import Fantasquadra, Giocatore, Operazione, operazione_giocatori


INVERSE_OPERATION_DEFINITIONS = {
    "acquisto definitivo": {
        "inverse_action_type": "undo_acquisto_definitivo",
        "description": (
            "Restore player ownership/values and FM balances to the state "
            "before the definitive transfer."
        ),
    },
    "scambio definitivo": {
        "inverse_action_type": "undo_scambio_definitivo",
        "description": (
            "Restore exchanged players and both teams' FM balances to the "
            "pre-exchange state."
        ),
    },
    "prestito": {
        "inverse_action_type": "undo_prestito",
        "description": (
            "Restore loan fields, convocato flags and FM balances to the "
            "pre-loan state."
        ),
    },
    "scambio prestiti": {
        "inverse_action_type": "undo_scambio_prestiti",
        "description": (
            "Restore loan fields for both groups of players and FM balances."
        ),
    },
    "svincolo": {
        "inverse_action_type": "undo_svincolo",
        "description": (
            "Recreate released players from before snapshots and restore the "
            "team FM balance."
        ),
    },
    "svincolo fine contratto": {
        "inverse_action_type": "undo_svincolo_fine_contratto",
        "description": (
            "Recreate players released at contract expiry without changing "
            "the team FM balance."
        ),
    },
    "asta": {
        "inverse_action_type": "undo_asta",
        "description": (
            "Remove auction-created players and restore the buyer team's FM "
            "balance."
        ),
    },
    "aumento contratto": {
        "inverse_action_type": "undo_aumento_contratto",
        "description": (
            "Restore contract expiry dates and refund the aumento cost to the "
            "team."
        ),
    },
}


@dataclass
class SemanticUndoEntry:
    entity_type: str
    entity_id: Optional[int]
    before_snapshot: Optional[dict[str, Any]]
    after_snapshot: Optional[dict[str, Any]]


@dataclass(frozen=True)
class UndoableTransaction:
    transaction_id: str
    operation_id: Optional[int]
    operation_type: str
    inverse_action_type: str
    created_at: str
    entity_count: int


@dataclass(frozen=True)
class SemanticUndoResult:
    transaction_id: str
    operation_type: str
    inverse_action_type: str
    restored_entities: int


class SemanticUndoConflict(RuntimeError):
    pass


class SemanticUndoBuilder:
    """Collect entity before/after snapshots for one auditable operation."""

    def __init__(
        self,
        operation_type: str,
        transaction_id: Optional[str] = None,
    ):
        self.operation_type = operation_type
        self.transaction_id = transaction_id or str(uuid.uuid4())
        self._entries: dict[tuple[str, Optional[int]], SemanticUndoEntry] = {}

    def capture_before(self, entity_type: str, obj) -> None:
        snapshot = model_snapshot(obj)
        key = (entity_type, snapshot.get("id"))
        if key not in self._entries:
            self._entries[key] = SemanticUndoEntry(
                entity_type=entity_type,
                entity_id=snapshot.get("id"),
                before_snapshot=snapshot,
                after_snapshot=None,
            )

    def capture_before_many(self, entity_type: str, objects) -> None:
        for obj in objects:
            self.capture_before(entity_type, obj)

    def capture_after(self, entity_type: str, obj) -> None:
        snapshot = model_snapshot(obj)
        key = (entity_type, snapshot.get("id"))
        entry = self._entries.get(key)
        if entry is None:
            entry = SemanticUndoEntry(
                entity_type=entity_type,
                entity_id=snapshot.get("id"),
                before_snapshot=None,
                after_snapshot=snapshot,
            )
            self._entries[key] = entry
        else:
            entry.after_snapshot = snapshot

    def capture_after_many(self, entity_type: str, objects) -> None:
        for obj in objects:
            self.capture_after(entity_type, obj)

    def mark_deleted(
        self,
        entity_type: str,
        entity_id: int,
        before_snapshot: dict[str, Any],
    ) -> None:
        key = (entity_type, entity_id)
        self._entries[key] = SemanticUndoEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            before_snapshot=before_snapshot,
            after_snapshot=None,
        )

    def write(self, session, operation_id: Optional[int]) -> None:
        definition = inverse_definition_for(self.operation_type)
        inverse_payload = {
            "transaction_id": self.transaction_id,
            "operation_id": operation_id,
            "operation_type": self.operation_type,
            "inverse_action_type": definition["inverse_action_type"],
            "description": definition["description"],
        }

        for entry in self._entries.values():
            session.execute(
                text(
                    """
                    INSERT INTO semantic_undo_log (
                        transaction_id,
                        operation_id,
                        action_type,
                        entity_type,
                        entity_id,
                        before_snapshot,
                        after_snapshot,
                        status,
                        operation_type,
                        inverse_action_type,
                        inverse_payload
                    )
                    VALUES (
                        :transaction_id,
                        :operation_id,
                        :action_type,
                        :entity_type,
                        :entity_id,
                        :before_snapshot,
                        :after_snapshot,
                        'active',
                        :operation_type,
                        :inverse_action_type,
                        :inverse_payload
                    )
                    """
                ),
                {
                    "transaction_id": self.transaction_id,
                    "operation_id": operation_id,
                    "action_type": "market_operation_registered",
                    "entity_type": entry.entity_type,
                    "entity_id": entry.entity_id,
                    "before_snapshot": json_or_none(entry.before_snapshot),
                    "after_snapshot": json_or_none(entry.after_snapshot),
                    "operation_type": self.operation_type,
                    "inverse_action_type": definition["inverse_action_type"],
                    "inverse_payload": json.dumps(
                        inverse_payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            )


def inverse_definition_for(operation_type: str) -> dict[str, str]:
    try:
        return INVERSE_OPERATION_DEFINITIONS[operation_type]
    except KeyError as exc:
        raise ValueError(
            f"Nessuna operazione inversa definita per: {operation_type}"
        ) from exc


def model_snapshot(obj) -> dict[str, Any]:
    mapper = inspect(obj).mapper
    snapshot: dict[str, Any] = {}
    for column in mapper.column_attrs:
        snapshot[column.key] = serialize_value(getattr(obj, column.key))

    if isinstance(obj, Operazione):
        try:
            snapshot["giocatore_ids"] = sorted(g.id for g in obj.giocatori)
        except Exception:
            snapshot["giocatore_ids"] = []

    return snapshot


def serialize_value(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def json_or_none(value: Optional[dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def list_undoable_transactions(session_factory, limit: int = 30) -> list[UndoableTransaction]:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        rows = session.execute(
            text(
                """
                SELECT transaction_id,
                       MIN(operation_id) AS operation_id,
                       MIN(operation_type) AS operation_type,
                       MIN(inverse_action_type) AS inverse_action_type,
                       MIN(created_at) AS created_at,
                       COUNT(*) AS entity_count
                FROM semantic_undo_log
                WHERE status = 'active'
                GROUP BY transaction_id
                ORDER BY MIN(id) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).mappings()
        return [
            UndoableTransaction(
                transaction_id=row["transaction_id"],
                operation_id=row["operation_id"],
                operation_type=row["operation_type"],
                inverse_action_type=row["inverse_action_type"],
                created_at=str(row["created_at"]),
                entity_count=row["entity_count"],
            )
            for row in rows
        ]
    finally:
        session.close()


def undo_transaction(
    session_factory,
    transaction_id: str,
    strict: bool = True,
) -> SemanticUndoResult:
    session = session_factory()
    try:
        rows = _load_active_rows(session, transaction_id)
        if not rows:
            raise ValueError(
                "Nessuna transazione semantica attiva trovata per: "
                + transaction_id
            )

        operation_type = rows[0]["operation_type"]
        inverse_action_type = rows[0]["inverse_action_type"]

        if strict:
            _validate_current_state(session, rows)

        restored_entities = _apply_inverse_snapshots(session, rows)
        session.execute(
            text(
                """
                UPDATE semantic_undo_log
                SET status = 'undone',
                    undone_at = CURRENT_TIMESTAMP,
                    undo_error = NULL
                WHERE transaction_id = :transaction_id
                """
            ),
            {"transaction_id": transaction_id},
        )
        session.commit()
        return SemanticUndoResult(
            transaction_id=transaction_id,
            operation_type=operation_type,
            inverse_action_type=inverse_action_type,
            restored_entities=restored_entities,
        )
    except Exception as exc:
        session.rollback()
        _record_undo_failure(session_factory, transaction_id, exc)
        raise
    finally:
        session.close()


def _load_active_rows(session, transaction_id: str) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT id, transaction_id, operation_id, operation_type,
                   inverse_action_type, entity_type, entity_id,
                   before_snapshot, after_snapshot
            FROM semantic_undo_log
            WHERE transaction_id = :transaction_id
              AND status = 'active'
            ORDER BY
                CASE entity_type
                    WHEN 'operazione' THEN 0
                    WHEN 'giocatore' THEN 1
                    WHEN 'fantasquadra' THEN 2
                    ELSE 3
                END,
                id
            """
        ),
        {"transaction_id": transaction_id},
    ).mappings()
    return [dict(row) for row in rows]


def _validate_current_state(session, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        after_snapshot = _json_dict(row["after_snapshot"])
        if after_snapshot is None:
            continue
        if row["entity_type"] == "operazione":
            # Operation rows may already have been manually removed from history;
            # core entity restoration can still be valid.
            continue

        current = _current_snapshot(session, row["entity_type"], row["entity_id"])
        if current is None:
            raise SemanticUndoConflict(
                f"Entita mancante prima dell'undo: "
                f"{row['entity_type']}:{row['entity_id']}"
            )
        if not _snapshot_matches(current, after_snapshot):
            raise SemanticUndoConflict(
                f"Entita modificata dopo la transazione: "
                f"{row['entity_type']}:{row['entity_id']}"
            )


def _apply_inverse_snapshots(session, rows: list[dict[str, Any]]) -> int:
    restored = 0

    for row in rows:
        if row["entity_type"] == "operazione":
            _delete_operation(session, row["entity_id"])
            restored += 1

    for row in rows:
        if row["entity_type"] == "giocatore":
            _restore_model_from_row(session, Giocatore, row)
            restored += 1

    for row in rows:
        if row["entity_type"] == "fantasquadra":
            _restore_model_from_row(session, Fantasquadra, row)
            restored += 1

    return restored


def _restore_model_from_row(session, model, row: dict[str, Any]) -> None:
    before_snapshot = _json_dict(row["before_snapshot"])
    entity_id = row["entity_id"]

    if before_snapshot is None:
        _delete_model(session, model, entity_id)
        return

    obj = session.get(model, entity_id)
    values = _coerce_snapshot_for_model(model, before_snapshot)
    if obj is None:
        obj = model(**values)
        session.add(obj)
    else:
        for key, value in values.items():
            setattr(obj, key, value)


def _delete_operation(session, operation_id: Optional[int]) -> None:
    if operation_id is None:
        return
    session.execute(
        operazione_giocatori.delete().where(
            operazione_giocatori.c.operazione_id == operation_id
        )
    )
    op = session.get(Operazione, operation_id)
    if op is not None:
        session.delete(op)


def _delete_model(session, model, entity_id: Optional[int]) -> None:
    if entity_id is None:
        return
    if model is Giocatore:
        session.execute(
            operazione_giocatori.delete().where(
                operazione_giocatori.c.giocatore_id == entity_id
            )
        )
    obj = session.get(model, entity_id)
    if obj is not None:
        session.delete(obj)


def _current_snapshot(session, entity_type: str, entity_id: Optional[int]):
    model = _model_for_entity_type(entity_type)
    if model is None or entity_id is None:
        return None
    obj = session.get(model, entity_id)
    if obj is None:
        return None
    return model_snapshot(obj)


def _model_for_entity_type(entity_type: str):
    return {
        "fantasquadra": Fantasquadra,
        "giocatore": Giocatore,
        "operazione": Operazione,
    }.get(entity_type)


def _snapshot_matches(current: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key, expected_value in expected.items():
        if key not in current:
            continue
        if current[key] != expected_value:
            return False
    return True


def _coerce_snapshot_for_model(model, snapshot: dict[str, Any]) -> dict[str, Any]:
    mapper = inspect(model).mapper
    values: dict[str, Any] = {}
    for column in mapper.column_attrs:
        key = column.key
        if key not in snapshot:
            continue
        values[key] = _coerce_value(snapshot[key], column.columns[0].type)
    return values


def _coerce_value(value, column_type):
    if value is None:
        return None
    type_name = type(column_type).__name__
    if type_name == "Date" and isinstance(value, str):
        return datetime.date.fromisoformat(value)
    if type_name == "Integer":
        return int(value)
    if type_name == "Float":
        return float(value)
    if type_name == "Boolean":
        return bool(value)
    return value


def _json_dict(raw: Optional[str]) -> Optional[dict[str, Any]]:
    if raw is None:
        return None
    return json.loads(raw)


def _record_undo_failure(session_factory, transaction_id: str, exc: Exception) -> None:
    session = session_factory()
    session.info["skip_hybrid_sync"] = True
    try:
        session.execute(
            text(
                """
                UPDATE semantic_undo_log
                SET status = 'failed',
                    undo_error = :undo_error
                WHERE transaction_id = :transaction_id
                  AND status = 'active'
                """
            ),
            {
                "transaction_id": transaction_id,
                "undo_error": str(exc),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
