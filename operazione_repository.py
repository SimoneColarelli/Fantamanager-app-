"""
Repository for Operazione — handles creation, listing, soft-ish deletion
(hard delete since operations are audit records), and eager-loading of
all relationships so the UI never hits a detached-instance error.
"""
from __future__ import annotations

import datetime
import json
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

    def calcola_svincolo(
        self,
        giocatore_ids: List[int],
        fq_id: int,
        data: Optional[datetime.date] = None,
        clausole: Optional[str] = None,
        sessions_to_expire: Optional[List] = None,
    ) -> Operazione:
        """
        Execute a 'svincolo':
          • Credit sum of valore_svincolo of each player to fq.fm.
          • Hard-delete each player from the DB.
          • Record Operazione (players linked before deletion via M2M insert).
        """
        for s in (sessions_to_expire or []):
            try:
                s.expire_all()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq = session.query(Fantasquadra).filter_by(id=fq_id).one()
            giocatori = session.query(Giocatore).filter(Giocatore.id.in_(giocatore_ids)).all()

            total_vs = sum(g.valore_svincolo or 0.0 for g in giocatori)
            fq.fm += int(round(total_vs))

            # Record the Operazione first, while players still exist
            data_norm = (data or datetime.date.today()).replace(day=1)
            snapshot = json.dumps([
                {"nome": g.nome, "valore_svincolo": g.valore_svincolo, "fine_prestito": None}
                for g in giocatori
            ])
            op = Operazione(
                fantasquadra_a_id=fq_id,
                fantasquadra_b_id=None,
                tipo_operazione="svincolo",
                conguaglio=0,
                conguaglio_da_id=None,
                data=data_norm,
                clausole=clausole or "",
                giocatori_snapshot=snapshot,
            )
            op.giocatori = giocatori
            session.add(op)
            session.flush()   # assigns op.id and writes M2M rows before deletion

            # Hard-delete players
            for g in giocatori:
                session.delete(g)

            session.commit()
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def calcola_scambio_prestiti(
        self,
        giocatori_data_a: List[dict],  # [{"id": int, "fine_prestito": date}, ...] from fq_a
        giocatori_data_b: List[dict],  # [{"id": int, "fine_prestito": date}, ...] from fq_b
        fq_a_id: int,
        fq_b_id: int,
        fm: int,                        # optional FM paid by fq_b to fq_a; may be 0
        inizio_prestito: datetime.date,
        clausole: Optional[str] = None,
        sessions_to_expire: Optional[List] = None,
    ) -> Operazione:
        """
        Execute a 'scambio prestiti':
          • Players from fq_a go on loan to fq_b (in_prestito_a = fq_b.nome).
          • Players from fq_b go on loan to fq_a (in_prestito_a = fq_a.nome).
          • squadra, spesa, fascia etc. unchanged on both sides.
          • FM balances updated if fm > 0 (fq_b pays fq_a).
          • Single atomic commit.
        """
        for s in (sessions_to_expire or []):
            try:
                s.expire_all()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_a = session.query(Fantasquadra).filter_by(id=fq_a_id).one()
            fq_b = session.query(Fantasquadra).filter_by(id=fq_b_id).one()

            ids_a = [d["id"] for d in giocatori_data_a]
            ids_b = [d["id"] for d in giocatori_data_b]
            giocatori_a = session.query(Giocatore).filter(Giocatore.id.in_(ids_a)).all() if ids_a else []
            giocatori_b = session.query(Giocatore).filter(Giocatore.id.in_(ids_b)).all() if ids_b else []

            fine_map_a = {d["id"]: d["fine_prestito"] for d in giocatori_data_a}
            fine_map_b = {d["id"]: d["fine_prestito"] for d in giocatori_data_b}

            inizio_norm = inizio_prestito.replace(day=1)

            # Players from fq_a → on loan to fq_b
            for g in giocatori_a:
                g.in_prestito_a   = fq_b.nome
                g.inizio_prestito = inizio_norm
                g.fine_prestito   = fine_map_a[g.id]
                g.convocato       = False

            # Players from fq_b → on loan to fq_a
            for g in giocatori_b:
                g.in_prestito_a   = fq_a.nome
                g.inizio_prestito = inizio_norm
                g.fine_prestito   = fine_map_b[g.id]
                g.convocato       = False

            if fm > 0:
                fq_a.fm += fm
                fq_b.fm -= fm

            op = Operazione(
                fantasquadra_a_id=fq_a_id,
                fantasquadra_b_id=fq_b_id,
                tipo_operazione="scambio prestiti",
                conguaglio=fm,
                conguaglio_da_id=fq_b_id if fm > 0 else None,
                data=inizio_norm,
                clausole=clausole or "",
            )
            op.giocatori = giocatori_a + giocatori_b
            session.add(op)
            session.commit()
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def calcola_prestito(
        self,
        giocatori_data: List[dict],   # [{"id": int, "fine_prestito": date}, ...]
        fq_prestante_id: int,
        fq_ricevente_id: int,
        fm: int,                       # may be 0
        inizio_prestito: datetime.date,
        clausole: Optional[str] = None,
        sessions_to_expire: Optional[List] = None,
    ) -> Operazione:
        """
        Execute a 'prestito':
          • Set in_prestito_a, inizio_prestito, fine_prestito, convocato on each player.
          • squadra, spesa, fascia, etc. are NOT changed (player stays registered to fq_prestante).
          • Update FM balances if fm > 0.
          • Record Operazione.
        """
        for s in (sessions_to_expire or []):
            try:
                s.expire_all()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_prestante = session.query(Fantasquadra).filter_by(id=fq_prestante_id).one()
            fq_ricevente = session.query(Fantasquadra).filter_by(id=fq_ricevente_id).one()

            ids = [d["id"] for d in giocatori_data]
            giocatori = session.query(Giocatore).filter(Giocatore.id.in_(ids)).all()
            fine_map = {d["id"]: d["fine_prestito"] for d in giocatori_data}

            # Normalise inizio to 1st of month
            inizio_norm = inizio_prestito.replace(day=1)

            for g in giocatori:
                g.in_prestito_a    = fq_ricevente.nome
                g.inizio_prestito  = inizio_norm
                g.fine_prestito    = fine_map[g.id]
                g.convocato        = False
                # squadra, spesa, fascia, quotazione etc. unchanged — player is on loan

            if fm > 0:
                fq_prestante.fm += fm
                fq_ricevente.fm  -= fm

            op = Operazione(
                fantasquadra_a_id=fq_prestante_id,
                fantasquadra_b_id=fq_ricevente_id,
                tipo_operazione="prestito",
                conguaglio=fm,
                conguaglio_da_id=fq_ricevente_id if fm > 0 else None,
                data=inizio_norm,
                clausole=clausole or "",
            )
            op.giocatori = giocatori
            session.add(op)
            session.commit()
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def calcola_scambio(
        self,
        giocatori_data_a: List[dict],  # players leaving fq_a → going to fq_b
        giocatori_data_b: List[dict],  # players leaving fq_b → going to fq_a
        fq_a_id: int,
        fq_b_id: int,
        fm: int,                        # optional FM paid by fq_b to fq_a
        data_acquisto: datetime.date,
        clausole: Optional[str] = None,
        sessions_to_expire: Optional[List] = None,
    ) -> Operazione:
        """
        Execute a 'scambio definitivo':
          • Players in giocatori_data_a move from fq_a → fq_b.
          • Players in giocatori_data_b move from fq_b → fq_a.
          • If fm > 0, fq_b pays fq_a: fq_a.fm += fm, fq_b.fm -= fm.
          • Single atomic commit.

        Amounts:
          amount_A = sum of valore_svincolo of players leaving fq_a  (what fq_b receives)
          amount_B = sum of valore_svincolo of players leaving fq_b + fm

          spesa for players going to fq_b  = amount_B * quot_i / tot_quotA
          spesa for players going to fq_a  = amount_A * quot_j / tot_quotB
          valore_svincolo for players → fq_b = amount_B * quot_i / tot_quotA
          valore_svincolo for players → fq_a = amount_B * quot_j / tot_quotB
            (note: spec says amount_B for valore_svincolo of B-players too)
        """
        from constants import calculate_fascia

        for s in (sessions_to_expire or []):
            try:
                s.expire_all()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_a = session.query(Fantasquadra).filter_by(id=fq_a_id).one()
            fq_b = session.query(Fantasquadra).filter_by(id=fq_b_id).one()

            ids_a = [d["id"] for d in giocatori_data_a]
            ids_b = [d["id"] for d in giocatori_data_b]
            giocatori_a = session.query(Giocatore).filter(Giocatore.id.in_(ids_a)).all() if ids_a else []
            giocatori_b = session.query(Giocatore).filter(Giocatore.id.in_(ids_b)).all() if ids_b else []

            quot_a = {d["id"]: d["quotazione"] for d in giocatori_data_a}
            quot_b = {d["id"]: d["quotazione"] for d in giocatori_data_b}

            tot_quotA = sum(quot_a[g.id] for g in giocatori_a)
            tot_quotB = sum(quot_b[g.id] for g in giocatori_b)

            # amount_A = current valore_svincolo of players leaving fq_a
            amount_A = sum(
                (g.valore_svincolo or 0.0) for g in giocatori_a
            )
            # amount_B = current valore_svincolo of players leaving fq_b + fm
            amount_B = sum(
                (g.valore_svincolo or 0.0) for g in giocatori_b
            ) + fm

            # Normalise data_acquisto
            data_norm = data_acquisto.replace(day=1)
            if data_norm.month in (1, 2):
                scadenza = datetime.date(data_norm.year + 2, 7, 1)
            else:
                scadenza = datetime.date(data_norm.year + 3, 7, 1)

            # ── Players A → fq_b ─────────────────────────────────────────
            if tot_quotA == 0 and giocatori_a:
                raise ValueError("La somma delle quotazioni dei giocatori A è zero.")
            for g in giocatori_a:
                q_i     = quot_a[g.id]
                spesa_i = round(amount_B * q_i / tot_quotA, 2) if tot_quotA else 0.0
                g.squadra            = fq_b.nome
                g.spesa              = spesa_i
                g.data_acquisto      = data_norm
                g.fascia             = str(calculate_fascia(int(spesa_i)))
                g.quotazione         = q_i
                g.dq                 = 0
                g.valore_svincolo    = spesa_i
                g.scadenza_contratto = scadenza
                g.convocato          = False
                g.in_serie_a         = True

            # ── Players B → fq_a ─────────────────────────────────────────
            if tot_quotB == 0 and giocatori_b:
                raise ValueError("La somma delle quotazioni dei giocatori B è zero.")
            for g in giocatori_b:
                q_j     = quot_b[g.id]
                spesa_j = round(amount_A * q_j / tot_quotB, 2) if tot_quotB else 0.0
                g.squadra            = fq_a.nome
                g.spesa              = spesa_j
                g.data_acquisto      = data_norm
                g.fascia             = str(calculate_fascia(int(spesa_j)))
                g.quotazione         = q_j
                g.dq                 = 0
                g.valore_svincolo    = spesa_j
                g.scadenza_contratto = scadenza
                g.convocato          = False
                g.in_serie_a         = True

            # ── FM balances ───────────────────────────────────────────────
            if fm > 0:
                fq_a.fm += fm
                fq_b.fm -= fm

            # ── Record Operazione ─────────────────────────────────────────
            op = Operazione(
                fantasquadra_a_id=fq_a_id,
                fantasquadra_b_id=fq_b_id,
                tipo_operazione="scambio definitivo",
                conguaglio=fm,
                conguaglio_da_id=fq_b_id if fm > 0 else None,
                data=data_norm,
                clausole=clausole or "",
            )
            op.giocatori = giocatori_a + giocatori_b
            session.add(op)
            session.commit()
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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

    # ------------------------------------------------------------------ #
    #  BUSINESS LOGIC — CESSIONE DEFINITIVA                                #
    # ------------------------------------------------------------------ #

    def calcola_acquisto(
        self,
        giocatori_data: List[dict],   # [{"id": int, "quotazione": int}, ...]
        fq_venditrice_id: int,
        fq_acquirente_id: int,
        fm: int,
        data_acquisto: datetime.date,
        clausole: Optional[str] = None,
        sessions_to_expire: Optional[List] = None,   # pass other open sessions
    ) -> Operazione:
        """
        Execute a 'acquisto definitivo' atomically inside a single fresh session:
          1. Update every Giocatore.
          2. Update both Fantasquadra.fm values.
          3. Record the Operazione.
        All steps are committed together; the session is closed when done.
        """
        from constants import calculate_fascia

        # ── Release any open read transactions in sibling sessions ───────
        # SQLite blocks writers when other connections hold read transactions.
        # Calling expire_all() forces SQLAlchemy to end those implicit reads
        # without closing the sessions themselves.
        for s in (sessions_to_expire or []):
            try:
                s.expire_all()
            except Exception:
                pass

        # ── Open a dedicated session for this entire operation ───────────
        session = self.session_factory()
        try:
            # ── Resolve objects ──────────────────────────────────────────
            fq_venditrice = session.query(Fantasquadra).filter_by(id=fq_venditrice_id).one()
            fq_acquirente = session.query(Fantasquadra).filter_by(id=fq_acquirente_id).one()

            giocatore_ids = [d["id"] for d in giocatori_data]
            giocatori = (
                session.query(Giocatore)
                .filter(Giocatore.id.in_(giocatore_ids))
                .all()
            )
            quot_override = {d["id"]: d["quotazione"] for d in giocatori_data}

            # ── Compute total quotazione ─────────────────────────────────
            tot_quot = sum(quot_override[g.id] for g in giocatori)
            if tot_quot == 0:
                raise ValueError(
                    "La somma delle quotazioni è zero: "
                    "impossibile calcolare la ripartizione."
                )

            # ── Normalise data_acquisto ──────────────────────────────────
            data_norm = data_acquisto.replace(day=1)

            # ── Compute scadenza_contratto ───────────────────────────────
            if data_norm.month in (1, 2):
                scadenza = datetime.date(data_norm.year + 2, 7, 1)
            else:
                scadenza = datetime.date(data_norm.year + 3, 7, 1)

            # ── Update each Giocatore ────────────────────────────────────
            for g in giocatori:
                q_i     = quot_override[g.id]
                spesa_i = round(fm * q_i / tot_quot, 2)

                g.squadra            = fq_acquirente.nome
                g.spesa              = spesa_i
                g.data_acquisto      = data_norm
                g.fascia             = str(calculate_fascia(int(spesa_i)))
                g.quotazione         = q_i
                g.dq                 = 0
                g.valore_svincolo    = spesa_i
                g.scadenza_contratto = scadenza
                g.convocato          = False
                g.in_serie_a         = True

            # ── Update Fantasquadra FM balances ──────────────────────────
            fq_venditrice.fm += fm
            fq_acquirente.fm -= fm

            # ── Record Operazione ────────────────────────────────────────
            op = Operazione(
                fantasquadra_a_id=fq_venditrice_id,
                fantasquadra_b_id=fq_acquirente_id,
                tipo_operazione="acquisto definitivo",
                conguaglio=fm,
                conguaglio_da_id=fq_acquirente_id,
                data=data_norm,
                clausole=clausole or "",
            )
            op.giocatori = giocatori
            session.add(op)

            # ── Single atomic commit ─────────────────────────────────────
            session.commit()

            # Detach the op so callers can read its id after session close
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()