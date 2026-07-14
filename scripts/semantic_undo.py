from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import Base, SessionLocal, engine
from migration_runner import run_migrations
from persistence.semantic_undo import list_undoable_transactions, undo_transaction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or execute semantic undo transactions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List undoable semantic transactions.")

    undo_parser = subparsers.add_parser("undo", help="Undo a semantic transaction.")
    undo_parser.add_argument("transaction_id", nargs="?", help="Transaction id to undo.")
    undo_parser.add_argument(
        "--latest",
        action="store_true",
        help="Undo the latest active semantic transaction.",
    )
    undo_parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Skip current-state conflict checks.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    Base.metadata.create_all(engine)
    run_migrations(engine)

    if args.command == "list":
        transactions = list_undoable_transactions(SessionLocal)
        if not transactions:
            print("No active semantic undo transactions.")
            return 0
        for item in transactions:
            print(
                f"{item.transaction_id} | {item.created_at} | "
                f"{item.operation_type} | op={item.operation_id} | "
                f"entities={item.entity_count}"
            )
        return 0

    if args.command == "undo":
        transaction_id = args.transaction_id
        if args.latest:
            transactions = list_undoable_transactions(SessionLocal, limit=1)
            if not transactions:
                print("No active semantic undo transactions.", file=sys.stderr)
                return 2
            transaction_id = transactions[0].transaction_id

        if not transaction_id:
            print("Provide a transaction_id or use --latest.", file=sys.stderr)
            return 2

        result = undo_transaction(
            SessionLocal,
            transaction_id=transaction_id,
            strict=not args.no_strict,
        )
        print(f"undone: {result.transaction_id}")
        print(f"operation_type: {result.operation_type}")
        print(f"inverse_action_type: {result.inverse_action_type}")
        print(f"restored_entities: {result.restored_entities}")
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
