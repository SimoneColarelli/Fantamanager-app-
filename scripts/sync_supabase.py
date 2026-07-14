from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import Base, SessionLocal, engine
from migration_runner import run_migrations
from persistence import create_hybrid_persistence_from_env
from persistence.sync_state import read_sync_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync Fantamanager SQLite data with the configured Supabase database."
    )
    parser.add_argument(
        "action",
        choices=("push", "pull", "status"),
        help="push local SQLite to Supabase, pull Supabase to SQLite, or show local sync state.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive pull from Supabase to local SQLite.",
    )
    return parser.parse_args()


def print_result(result) -> None:
    print(f"status: {result.status}")
    print(f"direction: {result.direction}")
    print(f"message: {result.message}")
    if result.counts:
        print("counts:")
        for table, count in result.counts.items():
            print(f"  {table}: {count}")
    if result.skipped_links:
        print(f"skipped_links: {len(result.skipped_links)}")


def main() -> int:
    args = parse_args()

    Base.metadata.create_all(engine)
    run_migrations(engine)

    manager = create_hybrid_persistence_from_env(SessionLocal, engine)

    if args.action == "status":
        print(f"configured: {manager.is_configured}")
        print(f"sync_mode: {manager.sync_mode}")
        state = read_sync_state(SessionLocal)
        for key in sorted(state):
            print(f"{key}: {state[key]}")
        return 0

    if not manager.is_configured:
        print(
            "Supabase is not configured. Set FANTAMANAGER_SUPABASE_DB_URL first.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.action == "push":
            result = manager.push_local_to_remote(
                reason="manual_cli",
                raise_on_error=True,
            )
        elif args.action == "pull":
            if not args.yes:
                print(
                    "Pull replaces the local SQLite data. Re-run with --yes to confirm.",
                    file=sys.stderr,
                )
                return 2
            result = manager.pull_remote_to_local(
                reason="manual_cli",
                raise_on_error=True,
            )
        else:
            raise AssertionError(args.action)
    finally:
        manager.stop()

    print_result(result)
    return 0 if result and result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
