"""Baseline migration.

The current project historically used SQLAlchemy create_all. This migration
records that baseline so future schema changes can be versioned explicitly.
"""

revision = "001_baseline"


def upgrade(connection):
    # Current schema is created from SQLAlchemy models before migrations run.
    return None
