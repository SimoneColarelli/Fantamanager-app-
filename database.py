from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///fantamanager.db"

# ── Engine ────────────────────────────────────────────────────────────────────
# check_same_thread=False is required for SQLite when the same connection is
# used across the main thread and any Qt signal invocations.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# ── WAL mode ──────────────────────────────────────────────────────────────────
# SQLite's default journal mode is "DELETE" which locks the entire database file
# for the duration of any write, blocking all other connections (even readers).
# WAL (Write-Ahead Logging) allows multiple concurrent readers alongside one
# writer — essential here because Repository sessions keep long-lived read
# transactions open while MercatoWidget needs to write atomically.
@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")   # wait up to 5 s before raising
    cursor.close()


# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# ── Declarative base ──────────────────────────────────────────────────────────
Base = declarative_base()