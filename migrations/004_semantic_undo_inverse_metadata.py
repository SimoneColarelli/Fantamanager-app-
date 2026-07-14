"""Add inverse-operation metadata to semantic undo log."""

from sqlalchemy import text


revision = "004_semantic_undo_inverse_metadata"


def upgrade(connection):
    existing_columns = {
        row[1]
        for row in connection.execute(text("PRAGMA table_info(semantic_undo_log)"))
    }

    additions = {
        "operation_type": "VARCHAR",
        "inverse_action_type": "VARCHAR",
        "inverse_payload": "TEXT",
    }
    for column_name, column_type in additions.items():
        if column_name not in existing_columns:
            connection.execute(
                text(
                    f"ALTER TABLE semantic_undo_log "
                    f"ADD COLUMN {column_name} {column_type}"
                )
            )
