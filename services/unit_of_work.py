from __future__ import annotations

from typing import Optional

from operazione_repository import OperazioneRepository


class UnitOfWork:
    """
    Application-level boundary for repository access.

    The current repositories still own several operation-specific transactions.
    This class centralizes their construction and lifecycle now, and gives us a
    single seam for moving transaction ownership out of repositories later.
    """

    def __init__(self, session_factory, operazione_repo: Optional[OperazioneRepository] = None):
        self.session_factory = session_factory
        self.operazioni = operazione_repo or OperazioneRepository(session_factory)

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        try:
            self.operazioni.session.close()
        except Exception:
            pass

    def rollback(self):
        try:
            self.operazioni.session.rollback()
        except Exception:
            pass
