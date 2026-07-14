from __future__ import annotations

import datetime
import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy import event

from persistence.env_loader import load_env_file
from persistence.snapshot_sync import SnapshotSyncGateway, SyncResult
from persistence.sync_state import write_sync_state


VALID_SYNC_MODES = {"off", "manual", "auto"}


@dataclass(frozen=True)
class HybridPersistenceConfig:
    remote_database_url: Optional[str]
    sync_mode: str = "off"
    pull_on_start: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.remote_database_url)

    @classmethod
    def from_env(cls) -> "HybridPersistenceConfig":
        load_env_file()
        url = (
            os.getenv("FANTAMANAGER_SUPABASE_DB_URL")
            or os.getenv("FANTAMANAGER_REMOTE_DATABASE_URL")
            or os.getenv("SUPABASE_DB_URL")
        )
        default_mode = "manual" if url else "off"
        sync_mode = os.getenv("FANTAMANAGER_SYNC_MODE", default_mode).strip().lower()
        if sync_mode not in VALID_SYNC_MODES:
            sync_mode = default_mode

        pull_on_start = (
            os.getenv("FANTAMANAGER_SYNC_PULL_ON_START", "").strip().lower()
            in {"1", "true", "yes", "y"}
        )

        return cls(
            remote_database_url=_normalize_database_url(url),
            sync_mode=sync_mode,
            pull_on_start=pull_on_start,
        )


def _normalize_database_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class HybridPersistenceManager:
    """Coordinates local SQLite persistence with an optional Supabase mirror."""

    def __init__(
        self,
        config: HybridPersistenceConfig,
        local_session_factory,
        local_engine: Engine,
    ):
        self.config = config
        self.local_session_factory = local_session_factory
        self.local_engine = local_engine
        self._remote_engine: Optional[Engine] = None
        self._gateway: Optional[SnapshotSyncGateway] = None
        self._listening = False
        self._syncing = False
        self.last_result: Optional[SyncResult] = None

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    @property
    def sync_mode(self) -> str:
        return self.config.sync_mode

    def start(self) -> None:
        if not self.is_configured or self.sync_mode == "off":
            self._record_state(
                **{
                    "hybrid_sync.status": "disabled",
                    "hybrid_sync.last_message": "Supabase sync is not configured.",
                }
            )
            return

        if self.config.pull_on_start:
            startup_result = self.pull_remote_to_local(reason="startup")
            if startup_result is not None and not startup_result.ok:
                return

        if self.sync_mode == "auto" and not self._listening:
            event.listen(Session, "after_commit", self._on_after_commit)
            self._listening = True

        self._record_state(
            **{
                "hybrid_sync.status": "ready",
                "hybrid_sync.last_message": (
                    f"Supabase sync ready in {self.sync_mode} mode."
                ),
            }
        )

    def stop(self) -> None:
        if self._listening:
            try:
                if event.contains(Session, "after_commit", self._on_after_commit):
                    event.remove(Session, "after_commit", self._on_after_commit)
            finally:
                self._listening = False

        if self._remote_engine is not None:
            self._remote_engine.dispose()

    def push_local_to_remote(
        self,
        reason: str = "manual",
        raise_on_error: bool = False,
    ) -> Optional[SyncResult]:
        if not self.is_configured or self.sync_mode == "off":
            result = self._disabled_result("push")
            self.last_result = result
            self._record_result(result, reason)
            return result

        if self._syncing:
            return self.last_result

        self._syncing = True
        try:
            self._record_state(
                **{
                    "hybrid_sync.status": "pending",
                    "hybrid_sync.last_message": f"Push started: {reason}",
                }
            )
            result = self._gateway_or_create().push_local_to_remote()
            self.last_result = result
            self._record_result(result, reason)
            return result
        except Exception as exc:
            result = self._error_result("push", exc)
            self.last_result = result
            self._record_result(result, reason)
            if raise_on_error:
                raise
            return result
        finally:
            self._syncing = False

    def pull_remote_to_local(
        self,
        reason: str = "manual",
        raise_on_error: bool = False,
    ) -> Optional[SyncResult]:
        if not self.is_configured or self.sync_mode == "off":
            result = self._disabled_result("pull")
            self.last_result = result
            self._record_result(result, reason)
            return result

        if self._syncing:
            return self.last_result

        self._syncing = True
        try:
            self._record_state(
                **{
                    "hybrid_sync.status": "pending",
                    "hybrid_sync.last_message": f"Pull started: {reason}",
                }
            )
            result = self._gateway_or_create().pull_remote_to_local(self.local_engine)
            self.last_result = result
            self._record_result(result, reason)
            return result
        except Exception as exc:
            result = self._error_result("pull", exc)
            self.last_result = result
            self._record_result(result, reason)
            if raise_on_error:
                raise
            return result
        finally:
            self._syncing = False

    def _on_after_commit(self, session) -> None:
        if self._syncing:
            return
        if session.info.get("skip_hybrid_sync"):
            return
        if self.sync_mode != "auto":
            return
        if not self._is_local_session(session):
            return

        self.push_local_to_remote(reason="after_commit")

    def _is_local_session(self, session) -> bool:
        try:
            bind = session.get_bind()
        except Exception:
            return False

        if bind is self.local_engine:
            return True

        try:
            return str(bind.url) == str(self.local_engine.url)
        except Exception:
            return False

    def _gateway_or_create(self) -> SnapshotSyncGateway:
        if self._gateway is not None:
            return self._gateway

        if not self.config.remote_database_url:
            raise RuntimeError("Supabase database URL is not configured.")

        self._remote_engine = create_engine(
            self.config.remote_database_url,
            pool_pre_ping=True,
            future=True,
        )
        self._gateway = SnapshotSyncGateway(
            local_session_factory=self.local_session_factory,
            remote_engine=self._remote_engine,
        )
        return self._gateway

    def _disabled_result(self, direction: str) -> SyncResult:
        now = datetime.datetime.now(datetime.UTC)
        return SyncResult(
            status="disabled",
            direction=direction,
            started_at=now,
            finished_at=now,
            message="Supabase sync is disabled or not configured.",
        )

    def _error_result(self, direction: str, exc: Exception) -> SyncResult:
        now = datetime.datetime.now(datetime.UTC)
        return SyncResult(
            status="error",
            direction=direction,
            started_at=now,
            finished_at=now,
            message=str(exc),
        )

    def _record_result(self, result: SyncResult, reason: str) -> None:
        values = {
            "hybrid_sync.status": result.status,
            "hybrid_sync.direction": result.direction,
            "hybrid_sync.reason": reason,
            "hybrid_sync.last_attempt_at": result.started_at,
            "hybrid_sync.last_finished_at": result.finished_at,
            "hybrid_sync.last_message": result.message,
            "hybrid_sync.last_counts": result.counts,
            "hybrid_sync.skipped_links": result.skipped_links,
        }
        if result.ok:
            values["hybrid_sync.last_success_at"] = result.finished_at
        self._record_state(**values)

    def _record_state(self, **values) -> None:
        try:
            write_sync_state(self.local_session_factory, values)
        except Exception:
            pass


def create_hybrid_persistence_from_env(
    local_session_factory,
    local_engine: Engine,
) -> HybridPersistenceManager:
    return HybridPersistenceManager(
        config=HybridPersistenceConfig.from_env(),
        local_session_factory=local_session_factory,
        local_engine=local_engine,
    )
