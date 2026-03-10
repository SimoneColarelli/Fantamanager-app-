"""
Repository for Operazione — handles creation, listing, soft-ish deletion
(hard delete since operations are audit records), and eager-loading of
all relationships so the UI never hits a detached-instance error.
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from sqlalchemy.orm import joinedload

from models import Operazione, Giocatore, Fantasquadra, TIPI_OPERAZIONE


class OperazioneRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session = session_factory()

    # ------------------------------------------------------------------ #
    #  READ                                                                #
    # ------------------------------------------------------------------ #

    def all(self) -> List[Operazione]:
        """Return all operations, newest first, with all relationships loaded."""
        fresh = self.session_factory()
        try:
            results = (
                fresh.query(Operazione)
                .options(
                    joinedload(Operazione.giocatori),
                    joinedload(Operazione.fantasquadra_a),
                    joinedload(Operazione.fantasquadra_b),
                    joinedload(Operazione.conguaglio_da),
                )
                .order_by(Operazione.id.desc())
                .all()
            )
            fresh.expunge_all()
            return results
        finally:
            fresh.close()

    def get(self, operazione_id: int) -> Optional[Operazione]:
        fresh = self.session_factory()
        try:
            result = (
                fresh.query(Operazione)
                .options(
                    joinedload(Operazione.giocatori),
                    joinedload(Operazione.fantasquadra_a),
                    joinedload(Operazione.fantasquadra_b),
                    joinedload(Operazione.conguaglio_da),
                )
                .filter_by(id=operazione_id)
                .one_or_none()
            )
            if result:
                fresh.expunge_all()
            return result
        finally:
            fresh.close()

    # ------------------------------------------------------------------ #
    #  WRITE                                                               #
    # ------------------------------------------------------------------ #

    def create(
        self,
        fantasquadra_a_id: int,
        tipo_operazione: str,
        giocatore_ids: List[int],
        fantasquadra_b_id: Optional[int] = None,
        conguaglio: int = 0,
        conguaglio_da_id: Optional[int] = None,
        data: Optional[datetime.date] = None,
        clausole: Optional[str] = None,
    ) -> Operazione:
        if tipo_operazione not in TIPI_OPERAZIONE:
            raise ValueError(f"Tipo operazione non valido: {tipo_operazione}")

        session = self.session
        giocatori = session.query(Giocatore).filter(Giocatore.id.in_(giocatore_ids)).all()

        op = Operazione(
            fantasquadra_a_id=fantasquadra_a_id,
            fantasquadra_b_id=fantasquadra_b_id,
            tipo_operazione=tipo_operazione,
            conguaglio=conguaglio or 0,
            conguaglio_da_id=conguaglio_da_id,
            data=data,
            clausole=clausole or "",
        )
        op.giocatori = giocatori

        session.add(op)
        session.commit()
        session.refresh(op)
        return op

    def delete(self, operazione_id: int) -> bool:
        """Hard-delete an operation (operations are audit records; no soft delete needed)."""
        session = self.session
        op = session.query(Operazione).filter_by(id=operazione_id).one_or_none()
        if op is None:
            return False
        session.delete(op)
        session.commit()
        return True

    # ------------------------------------------------------------------ #
    #  HELPERS                                                             #
    # ------------------------------------------------------------------ #

    def active_fantasquadre(self) -> List[Fantasquadra]:
        fresh = self.session_factory()
        try:
            results = fresh.query(Fantasquadra).filter_by(deleted=False).order_by(Fantasquadra.nome).all()
            fresh.expunge_all()
            return results
        finally:
            fresh.close()

    def active_giocatori(self) -> List[Giocatore]:
        fresh = self.session_factory()
        try:
            results = (
                fresh.query(Giocatore)
                .filter_by(deleted=False)
                .order_by(Giocatore.nome)
                .all()
            )
            fresh.expunge_all()
            return results
        finally:
            fresh.close()

    def giocatori_by_squadra(self, squadra_nome: str) -> List[Giocatore]:
        """Return active players belonging to the given fantasquadra name,
        ordered by name.  quotazione and valore_svincolo are loaded as-is."""
        fresh = self.session_factory()
        try:
            results = (
                fresh.query(Giocatore)
                .filter_by(deleted=False, squadra=squadra_nome)
                .order_by(Giocatore.nome)
                .all()
            )
            fresh.expunge_all()
            return results
        finally:
            fresh.close()