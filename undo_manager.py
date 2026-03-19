"""
UndoManager — snapshot-based undo for Fantamanager.

Strategy
--------
Before every Session.commit() we copy fantamanager.db to a temp directory,
keeping the last MAX_SNAPSHOTS copies.  Undo = close every open connection,
overwrite the live DB file with the chosen snapshot, then hand fresh sessions
back to every Repository that needs one.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from collections import deque
from typing import Callable, Deque, List, Optional

from sqlalchemy.engine import Engine


class UndoManager:

    def __init__(self, db_path: str, engine: Engine, max_snapshots: int = 5):
        self.db_path       = os.path.abspath(db_path)
        self.engine        = engine
        self.max_snapshots = max_snapshots

        self._tmpdir: str        = tempfile.mkdtemp(prefix="fantamanager_undo_")
        self._snapshots: Deque[str] = deque()
        self._refresh_callbacks: List[Callable] = []
        # Called after every snapshot save (i.e. after every commit)
        self._snapshot_callbacks: List[Callable] = []
        self._counter: int       = 0   # monotonic, never resets

        # Populated by MainWindow after construction:
        #   list of (repository_or_session, session_factory) tuples so we can
        #   close the old session and assign a fresh one after restore.
        self._all_sessions: List = []   # kept for API compat / expire_all
        # List of Repository objects whose .session must be replaced after undo
        self._repos: List = []

        self._listening = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Take a baseline snapshot and start listening for commits."""
        if self._listening:
            return
        self._listening = True
        self._save_snapshot()

        from sqlalchemy import event as _ev
        from sqlalchemy.orm import Session
        _ev.listen(Session, "before_commit", self._on_session_commit)

    def stop(self):
        """Stop listening and clean up temp files."""
        try:
            from sqlalchemy import event as _ev
            from sqlalchemy.orm import Session
            if _ev.contains(Session, "before_commit", self._on_session_commit):
                _ev.remove(Session, "before_commit", self._on_session_commit)
        except Exception:
            pass
        self._cleanup()

    def register_refresh_callback(self, cb: Callable):
        self._refresh_callbacks.append(cb)

    def register_snapshot_callback(self, cb: Callable):
        """Register a no-arg callable called after every commit snapshot."""
        self._snapshot_callbacks.append(cb)

    def can_undo(self) -> bool:
        return len(self._snapshots) > 0

    def undo_count(self) -> int:
        return len(self._snapshots)

    def undo(self) -> bool:
        """
        Restore the most recent snapshot.
        Closes all registered sessions, replaces the DB file, opens fresh
        sessions on all registered repos, then fires refresh callbacks.
        """
        if not self._snapshots:
            return False

        snapshot_path = self._snapshots.pop()

        try:
            # 1. Close every open session to release OS file locks
            self._close_all_sessions()

            # 2. Release all pooled connections in the engine
            self.engine.dispose()

            # 3. Overwrite the live DB with the snapshot
            shutil.copy2(snapshot_path, self.db_path)

            # 4. Handle WAL / SHM files
            for ext in ("-wal", "-shm"):
                live = self.db_path + ext
                snap = snapshot_path + ext
                if os.path.exists(snap):
                    shutil.copy2(snap, live)
                elif os.path.exists(live):
                    try:
                        os.remove(live)
                    except Exception:
                        pass

            # 5. Clean up the snapshot file
            for f in (snapshot_path, snapshot_path + "-wal",
                      snapshot_path + "-shm"):
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

            # 6. Give every registered repo a brand-new session
            self._reopen_sessions()

        except Exception as e:
            # Put snapshot back so the step isn't lost
            self._snapshots.append(snapshot_path)
            raise RuntimeError(f"Undo failed: {e}") from e

        # 7. Fire all refresh callbacks
        for cb in self._refresh_callbacks:
            try:
                cb()
            except Exception:
                pass

        return True

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_session_commit(self, session):
        """Called by SQLAlchemy before every session.commit() — captures state before the change."""
        self._save_snapshot()

    def _save_snapshot(self):
        """Copy the current DB (+ WAL) into the temp directory."""
        if not os.path.exists(self.db_path):
            return

        self._counter += 1
        dest = os.path.join(self._tmpdir, f"snap_{self._counter:06d}.db")

        try:
            shutil.copy2(self.db_path, dest)
            wal = self.db_path + "-wal"
            if os.path.exists(wal):
                shutil.copy2(wal, dest + "-wal")
        except Exception:
            return

        self._snapshots.append(dest)

        # Notify snapshot callbacks (e.g. to update the undo menu action)
        for cb in self._snapshot_callbacks:
            try:
                cb()
            except Exception:
                pass

        # Evict oldest when over the limit
        while len(self._snapshots) > self.max_snapshots:
            old = self._snapshots.popleft()
            for f in (old, old + "-wal", old + "-shm"):
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

    def _close_all_sessions(self):
        """Close every open session so SQLite releases its file handle."""
        for s in self._all_sessions:
            try:
                s.close()
            except Exception:
                pass
        # Also close sessions held directly by registered repos
        for repo in self._repos:
            try:
                repo.session.close()
            except Exception:
                pass

    def _reopen_sessions(self):
        """
        Create fresh sessions for every registered repository.
        Each repo keeps `session_factory` so we can call it again.
        """
        for repo in self._repos:
            try:
                repo.session = repo.session_factory()
            except Exception:
                pass

    def _cleanup(self):
        try:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception:
            pass