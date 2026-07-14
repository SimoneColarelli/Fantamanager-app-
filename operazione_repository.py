"""
Repository for Operazione — handles creation, listing, soft-ish deletion
(hard delete since operations are audit records), and eager-loading of
all relationships so the UI never hits a detached-instance error.
"""
from __future__ import annotations

import datetime
import json
from typing import Any, List, Optional

from sqlalchemy.orm import joinedload

from models import Operazione, Giocatore, Fantasquadra, TIPI_OPERAZIONE
from persistence.semantic_undo import SemanticUndoBuilder, model_snapshot


class OperazioneRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session = session_factory()

    @staticmethod
    def _assign_team(giocatore: Giocatore, fantasquadra: Fantasquadra) -> None:
        giocatore.squadra = fantasquadra.nome
        giocatore.fantasquadra_id = fantasquadra.id

    @staticmethod
    def _assign_loan_to(giocatore: Giocatore, fantasquadra: Fantasquadra) -> None:
        giocatore.in_prestito_a = fantasquadra.nome
        giocatore.prestito_a_fantasquadra_id = fantasquadra.id

    @staticmethod
    def _clear_loan(giocatore: Giocatore) -> None:
        giocatore.in_prestito_a = None
        giocatore.prestito_a_fantasquadra_id = None
        giocatore.inizio_prestito = None
        giocatore.fine_prestito = None

    @staticmethod
    def _snapshot_map(objects) -> dict[int, dict[str, Any]]:
        return {obj.id: model_snapshot(obj) for obj in objects}

    @staticmethod
    def _indexed_details(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        indexed = {}
        for row in rows:
            entity_id = row.get("id") or row.get("giocatore_id")
            if entity_id is not None:
                indexed[int(entity_id)] = row
        return indexed

    @staticmethod
    def _snapshot_json(
        op: Operazione,
        *,
        fq_a_before: Optional[dict[str, Any]] = None,
        fq_a_after: Optional[dict[str, Any]] = None,
        fq_b_before: Optional[dict[str, Any]] = None,
        fq_b_after: Optional[dict[str, Any]] = None,
        conguaglio_da_before: Optional[dict[str, Any]] = None,
        conguaglio_da_after: Optional[dict[str, Any]] = None,
        giocatori_before: Optional[dict[int, dict[str, Any]]] = None,
        giocatori_after: Optional[dict[int, dict[str, Any]]] = None,
        giocatori_details: Optional[list[dict[str, Any]]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> str:
        before = giocatori_before or {}
        after = giocatori_after or {}
        details_by_id = OperazioneRepository._indexed_details(giocatori_details or [])
        giocatore_ids = sorted(set(before) | set(after) | set(details_by_id))

        giocatori = []
        for giocatore_id in giocatore_ids:
            before_snapshot = before.get(giocatore_id)
            after_snapshot = after.get(giocatore_id)
            detail = details_by_id.get(giocatore_id)
            nome = (
                (after_snapshot or {}).get("nome")
                or (before_snapshot or {}).get("nome")
                or (detail or {}).get("nome")
            )
            giocatori.append(
                {
                    "id": giocatore_id,
                    "nome": nome,
                    "before": before_snapshot,
                    "after": after_snapshot,
                    "details": detail,
                }
            )

        payload = {
            "schema_version": 1,
            "operation_id": op.id,
            "tipo_operazione": op.tipo_operazione,
            "data": op.data.isoformat() if op.data else None,
            "clausole": op.clausole or "",
            "conguaglio": op.conguaglio or 0,
            "conguaglio_da_id": op.conguaglio_da_id,
            "fantasquadre": {
                "a": {"before": fq_a_before, "after": fq_a_after},
                "b": {"before": fq_b_before, "after": fq_b_after},
                "conguaglio_da": {
                    "before": conguaglio_da_before,
                    "after": conguaglio_da_after,
                },
            },
            "giocatori": giocatori,
            "extra": extra or {},
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

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
        undo = SemanticUndoBuilder(tipo_operazione)

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
        session.flush()
        undo.capture_after("operazione", op)
        undo.write(session, op.id)
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
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq = session.query(Fantasquadra).filter_by(id=fq_id).one()
            giocatori = session.query(Giocatore).filter(Giocatore.id.in_(giocatore_ids)).all()
            fq_before = model_snapshot(fq)
            giocatori_before = self._snapshot_map(giocatori)
            undo = SemanticUndoBuilder("svincolo")
            undo.capture_before("fantasquadra", fq)
            undo.capture_before_many("giocatore", giocatori)

            total_vs = sum(g.valore_svincolo or 0.0 for g in giocatori)
            fq.fm += int(round(total_vs))

            # Record the Operazione first, while players still exist
            data_norm = (data or datetime.date.today()).replace(day=1)
            snapshot_rows = [
                {
                    "id": g.id,
                    "nome": g.nome,
                    "valore_svincolo": g.valore_svincolo,
                    "fine_prestito": None,
                }
                for g in giocatori
            ]
            op = Operazione(
                fantasquadra_a_id=fq_id,
                fantasquadra_b_id=None,
                tipo_operazione="svincolo",
                conguaglio=0,
                conguaglio_da_id=None,
                data=data_norm,
                clausole=clausole or "",
            )
            op.giocatori = giocatori
            session.add(op)
            session.flush()   # assigns op.id and writes M2M rows before deletion
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_before,
                fq_a_after=model_snapshot(fq),
                giocatori_before=giocatori_before,
                giocatori_after={},
                giocatori_details=snapshot_rows,
                extra={"valore_svincolo_totale": total_vs},
            )
            undo.capture_after("fantasquadra", fq)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)

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
          • Players from fq_a go on loan to fq_b (legacy text + FK).
          • Players from fq_b go on loan to fq_a (legacy text + FK).
          • squadra, spesa, fascia etc. unchanged on both sides.
          • FM balances updated if fm > 0 (fq_b pays fq_a).
          • Single atomic commit.
        """
        for s in (sessions_to_expire or []):
            try:
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_a = session.query(Fantasquadra).filter_by(id=fq_a_id).one()
            fq_b = session.query(Fantasquadra).filter_by(id=fq_b_id).one()
            fq_a_before = model_snapshot(fq_a)
            fq_b_before = model_snapshot(fq_b)

            ids_a = [d["id"] for d in giocatori_data_a]
            ids_b = [d["id"] for d in giocatori_data_b]
            giocatori_a = session.query(Giocatore).filter(Giocatore.id.in_(ids_a)).all() if ids_a else []
            giocatori_b = session.query(Giocatore).filter(Giocatore.id.in_(ids_b)).all() if ids_b else []
            giocatori_before = self._snapshot_map(giocatori_a + giocatori_b)
            undo = SemanticUndoBuilder("scambio prestiti")
            undo.capture_before("fantasquadra", fq_a)
            undo.capture_before("fantasquadra", fq_b)
            undo.capture_before_many("giocatore", giocatori_a + giocatori_b)

            fine_map_a = {d["id"]: d["fine_prestito"] for d in giocatori_data_a}
            fine_map_b = {d["id"]: d["fine_prestito"] for d in giocatori_data_b}

            inizio_norm = inizio_prestito.replace(day=1)

            # Players from fq_a → on loan to fq_b
            for g in giocatori_a:
                self._assign_loan_to(g, fq_b)
                g.inizio_prestito = inizio_norm
                g.fine_prestito   = fine_map_a[g.id]
                g.convocato       = False

            # Players from fq_b → on loan to fq_a
            for g in giocatori_b:
                self._assign_loan_to(g, fq_a)
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
            session.flush()
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_a_before,
                fq_a_after=model_snapshot(fq_a),
                fq_b_before=fq_b_before,
                fq_b_after=model_snapshot(fq_b),
                conguaglio_da_before=fq_b_before if fm > 0 else None,
                conguaglio_da_after=model_snapshot(fq_b) if fm > 0 else None,
                giocatori_before=giocatori_before,
                giocatori_after=self._snapshot_map(giocatori_a + giocatori_b),
                giocatori_details=[
                    {
                        "id": g.id,
                        "direzione": "a_to_b",
                        "fine_prestito": fine_map_a[g.id].isoformat()
                        if fine_map_a[g.id]
                        else None,
                    }
                    for g in giocatori_a
                ]
                + [
                    {
                        "id": g.id,
                        "direzione": "b_to_a",
                        "fine_prestito": fine_map_b[g.id].isoformat()
                        if fine_map_b[g.id]
                        else None,
                    }
                    for g in giocatori_b
                ],
            )
            undo.capture_after("fantasquadra", fq_a)
            undo.capture_after("fantasquadra", fq_b)
            undo.capture_after_many("giocatore", giocatori_a + giocatori_b)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)
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
          • Set loan target text/FK, inizio_prestito, fine_prestito, convocato on each player.
          • squadra, spesa, fascia, etc. are NOT changed (player stays registered to fq_prestante).
          • Update FM balances if fm > 0.
          • Record Operazione.
        """
        for s in (sessions_to_expire or []):
            try:
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_prestante = session.query(Fantasquadra).filter_by(id=fq_prestante_id).one()
            fq_ricevente = session.query(Fantasquadra).filter_by(id=fq_ricevente_id).one()
            fq_prestante_before = model_snapshot(fq_prestante)
            fq_ricevente_before = model_snapshot(fq_ricevente)

            ids = [d["id"] for d in giocatori_data]
            giocatori = session.query(Giocatore).filter(Giocatore.id.in_(ids)).all()
            giocatori_before = self._snapshot_map(giocatori)
            fine_map = {d["id"]: d["fine_prestito"] for d in giocatori_data}
            undo = SemanticUndoBuilder("prestito")
            undo.capture_before("fantasquadra", fq_prestante)
            undo.capture_before("fantasquadra", fq_ricevente)
            undo.capture_before_many("giocatore", giocatori)

            # Normalise inizio to 1st of month
            inizio_norm = inizio_prestito.replace(day=1)

            for g in giocatori:
                self._assign_loan_to(g, fq_ricevente)
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
            session.flush()
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_prestante_before,
                fq_a_after=model_snapshot(fq_prestante),
                fq_b_before=fq_ricevente_before,
                fq_b_after=model_snapshot(fq_ricevente),
                conguaglio_da_before=fq_ricevente_before if fm > 0 else None,
                conguaglio_da_after=model_snapshot(fq_ricevente) if fm > 0 else None,
                giocatori_before=giocatori_before,
                giocatori_after=self._snapshot_map(giocatori),
                giocatori_details=[
                    {
                        "id": g.id,
                        "fine_prestito": fine_map[g.id].isoformat()
                        if fine_map[g.id]
                        else None,
                    }
                    for g in giocatori
                ],
            )
            undo.capture_after("fantasquadra", fq_prestante)
            undo.capture_after("fantasquadra", fq_ricevente)
            undo.capture_after_many("giocatore", giocatori)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)
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
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq_a = session.query(Fantasquadra).filter_by(id=fq_a_id).one()
            fq_b = session.query(Fantasquadra).filter_by(id=fq_b_id).one()
            fq_a_before = model_snapshot(fq_a)
            fq_b_before = model_snapshot(fq_b)

            ids_a = [d["id"] for d in giocatori_data_a]
            ids_b = [d["id"] for d in giocatori_data_b]
            giocatori_a = session.query(Giocatore).filter(Giocatore.id.in_(ids_a)).all() if ids_a else []
            giocatori_b = session.query(Giocatore).filter(Giocatore.id.in_(ids_b)).all() if ids_b else []
            giocatori_before = self._snapshot_map(giocatori_a + giocatori_b)
            undo = SemanticUndoBuilder("scambio definitivo")
            undo.capture_before("fantasquadra", fq_a)
            undo.capture_before("fantasquadra", fq_b)
            undo.capture_before_many("giocatore", giocatori_a + giocatori_b)

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
                self._assign_team(g, fq_b)
                self._clear_loan(g)
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
                self._assign_team(g, fq_a)
                self._clear_loan(g)
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
            session.flush()
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_a_before,
                fq_a_after=model_snapshot(fq_a),
                fq_b_before=fq_b_before,
                fq_b_after=model_snapshot(fq_b),
                conguaglio_da_before=fq_b_before if fm > 0 else None,
                conguaglio_da_after=model_snapshot(fq_b) if fm > 0 else None,
                giocatori_before=giocatori_before,
                giocatori_after=self._snapshot_map(giocatori_a + giocatori_b),
                giocatori_details=[
                    {
                        "id": g.id,
                        "direzione": "a_to_b",
                        "quotazione_usata": quot_a[g.id],
                    }
                    for g in giocatori_a
                ]
                + [
                    {
                        "id": g.id,
                        "direzione": "b_to_a",
                        "quotazione_usata": quot_b[g.id],
                    }
                    for g in giocatori_b
                ],
                extra={
                    "amount_a": amount_A,
                    "amount_b": amount_B,
                    "scadenza_contratto": scadenza.isoformat(),
                },
            )
            undo.capture_after("fantasquadra", fq_a)
            undo.capture_after("fantasquadra", fq_b)
            undo.capture_after_many("giocatore", giocatori_a + giocatori_b)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)
            session.commit()
            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  BUSINESS LOGIC — IMPORTA ASTA                                       #
    # ------------------------------------------------------------------ #

    def importa_asta(
        self,
        asta_data: List[dict],
        # [{"ext_id": int, "nome": str, "quotazione": int,
        #   "fq_nome": str, "spesa": int}, ...]
        data_asta: datetime.date,
        sessions_to_expire: Optional[List] = None,
    ) -> List[Operazione]:
        """
        Import an auction result.

        For each fantasquadra that appears in asta_data:
          1. CREATE new Giocatore rows (players don't exist in DB yet).
          2. Deduct total spesa from that fantasquadra's FM balance.
          3. Record one 'asta' Operazione per fantasquadra.

        Returns the list of created Operazione objects.
        """
        from constants import calculate_fascia

        for s in (sessions_to_expire or []):
            try:
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            # Normalise data and compute scadenza_contratto
            data_norm = data_asta.replace(day=1)
            if data_norm.month in (1, 2):
                scadenza = datetime.date(data_norm.year + 2, 7, 1)
            else:
                scadenza = datetime.date(data_norm.year + 3, 7, 1)

            # Map fantasquadra name → object (need to mutate .fm)
            fqs = session.query(Fantasquadra).filter_by(deleted=False).all()
            fq_obj_map = {fq.nome: fq for fq in fqs}
            fq_map = {fq.nome: fq.id for fq in fqs}

            # Group purchases by fantasquadra name
            from collections import defaultdict
            by_fq: dict = defaultdict(list)
            for row in asta_data:
                by_fq[row["fq_nome"]].append(row)

            created_ops: List[Operazione] = []

            for fq_nome, rows in by_fq.items():
                fq_id = fq_map.get(fq_nome)
                fq    = fq_obj_map.get(fq_nome)
                if fq_id is None or fq is None:
                    raise ValueError(
                        f"Fantasquadra '{fq_nome}' non trovata nel database. "
                        f"Verifica che il nome nel file CSV corrisponda esattamente."
                    )
                fq_before = model_snapshot(fq)
                undo = SemanticUndoBuilder("asta")
                undo.capture_before("fantasquadra", fq)

                new_giocatori: List[Giocatore] = []
                for row in rows:
                    spesa = float(row["spesa"])
                    g = Giocatore(
                        nome             = row["nome"],
                        squadra          = fq_nome,
                        fantasquadra_id   = fq_id,
                        spesa            = spesa,
                        data_acquisto    = data_norm,
                        fascia           = str(calculate_fascia(int(spesa))),
                        quotazione       = row["quotazione"],
                        dq               = 0,
                        valore_svincolo  = spesa,
                        scadenza_contratto = scadenza,
                        in_prestito_a    = None,
                        prestito_a_fantasquadra_id = None,
                        inizio_prestito  = None,
                        fine_prestito    = None,
                        convocato        = False,
                        in_serie_a       = True,
                        deleted          = False,
                    )
                    session.add(g)
                    new_giocatori.append(g)

                # Flush so giocatori get their PKs before linking to Operazione
                session.flush()

                total_fm = int(sum(row["spesa"] for row in rows))

                # Deduct FM spent at auction from this fantasquadra
                fq.fm -= total_fm

                op = Operazione(
                    fantasquadra_a_id  = fq_id,
                    fantasquadra_b_id  = None,
                    tipo_operazione    = "asta",
                    conguaglio         = total_fm,
                    conguaglio_da_id   = fq_id,
                    data               = data_norm,
                    clausole           = f"Asta avvenuta in data {data_asta.strftime('%d/%m/%Y')}",
                )
                op.giocatori = new_giocatori
                session.add(op)
                session.flush()
                op.operation_snapshot = self._snapshot_json(
                    op,
                    fq_a_before=fq_before,
                    fq_a_after=model_snapshot(fq),
                    conguaglio_da_before=fq_before,
                    conguaglio_da_after=model_snapshot(fq),
                    giocatori_before={},
                    giocatori_after=self._snapshot_map(new_giocatori),
                    giocatori_details=[
                        {
                            "id": g.id,
                            "quotazione_usata": g.quotazione,
                            "spesa": g.spesa,
                        }
                        for g in new_giocatori
                    ],
                    extra={"scadenza_contratto": scadenza.isoformat()},
                )
                undo.capture_after("fantasquadra", fq)
                undo.capture_after_many("giocatore", new_giocatori)
                undo.capture_after("operazione", op)
                undo.write(session, op.id)
                created_ops.append(op)

            session.commit()

            # Expunge so callers can read attributes after session close
            for op in created_ops:
                try:
                    session.expunge(op)
                except Exception:
                    pass

            return created_ops

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


    def calcola_asta_manuale(
        self,
        fq_id: int,
        giocatori_data: List[dict],
        # [{"nome": str, "quotazione": int, "spesa": int, "estendi": bool}, ...]
        data_asta: datetime.date = None,
        sessions_to_expire: Optional[List] = None,
    ) -> "Operazione":
        """
        Register a manual asta entry for a single fantasquadra.

        For each player in giocatori_data:
          - Creates a new Giocatore row with all required fields.
          - spesa = valore_svincolo = amount paid at auction.
          - scadenza_contratto computed from data_acquisto.
          - Deducts total spesa from fq.fm.
          - Optionally applies aumento contratto to rows marked with estendi=True.
        Records one 'asta' Operazione linking all created players and, when
        requested, one 'aumento contratto' Operazione for the extensions.
        """
        from constants import calculate_fascia

        for s in (sessions_to_expire or []):
            try:
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq = session.query(Fantasquadra).filter_by(id=fq_id).one()
            fq_before = model_snapshot(fq)
            undo = SemanticUndoBuilder("asta")
            undo.capture_before("fantasquadra", fq)

            # Normalise the single shared date for all players
            data_norm = (data_asta or datetime.date.today()).replace(day=1)
            if data_norm.month in (1, 2):
                scadenza = datetime.date(data_norm.year + 2, 7, 1)
            else:
                scadenza = datetime.date(data_norm.year + 3, 7, 1)

            new_giocatori: List[Giocatore] = []
            total_fm = 0
            estendi_giocatori: List[Giocatore] = []

            for row in giocatori_data:
                spesa = float(row["spesa"])

                g = Giocatore(
                    nome               = row["nome"],
                    squadra            = fq.nome,
                    fantasquadra_id     = fq_id,
                    spesa              = spesa,
                    data_acquisto      = data_norm,
                    fascia             = str(calculate_fascia(int(spesa))),
                    quotazione         = int(row["quotazione"]),
                    dq                 = 0,
                    valore_svincolo    = spesa,
                    scadenza_contratto = scadenza,
                    in_prestito_a      = None,
                    prestito_a_fantasquadra_id = None,
                    inizio_prestito    = None,
                    fine_prestito      = None,
                    convocato          = False,
                    in_serie_a         = True,
                    deleted            = False,
                )
                session.add(g)
                new_giocatori.append(g)
                total_fm += int(spesa)
                if row.get("estendi"):
                    estendi_giocatori.append(g)

            # Flush to get PKs before linking to Operazione
            session.flush()
            asta_giocatori_after = self._snapshot_map(new_giocatori)

            aumento_total = 0
            aumento_snapshot = []
            for g in estendi_giocatori:
                costo, anni_extra, nuova_scadenza = self.calcola_costo_aumento(g)
                aumento_total += costo
                aumento_snapshot.append({
                    "id":             g.id,
                    "nome":           g.nome,
                    "costo":          costo,
                    "nuova_scadenza": nuova_scadenza.isoformat(),
                    "anni_extra":     anni_extra,
                })
                g.scadenza_contratto = nuova_scadenza

            if estendi_giocatori and fq.fm - total_fm < aumento_total:
                raise ValueError(
                    fq.nome + " non ha abbastanza FM per l'aumento contratto "
                    "dopo l'asta (servono " + str(aumento_total) +
                    " FM, disponibili dopo asta " + str(fq.fm - total_fm) + " FM)."
                )

            # Deduct FM from fantasquadra
            fq.fm -= total_fm + aumento_total

            op = Operazione(
                fantasquadra_a_id = fq_id,
                fantasquadra_b_id = None,
                tipo_operazione   = "asta",
                conguaglio        = total_fm,
                conguaglio_da_id  = fq_id,
                data              = data_norm,
                clausole          = f"Asta avvenuta in data {data_asta.strftime('%d/%m/%Y')}",
            )
            op.giocatori = new_giocatori
            session.add(op)

            aumento_op = None
            if estendi_giocatori:
                aumento_op = Operazione(
                    fantasquadra_a_id  = fq_id,
                    fantasquadra_b_id  = None,
                    tipo_operazione    = "aumento contratto",
                    conguaglio         = aumento_total,
                    conguaglio_da_id   = fq_id,
                    data               = data_norm,
                    clausole           = "Aumento contratto contestuale ad asta",
                )
                aumento_op.giocatori = estendi_giocatori
                session.add(aumento_op)
            session.flush()
            fq_after = model_snapshot(fq)
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_before,
                fq_a_after=fq_after,
                conguaglio_da_before=fq_before,
                conguaglio_da_after=fq_after,
                giocatori_before={},
                giocatori_after=asta_giocatori_after,
                giocatori_details=[
                    {
                        "id": g.id,
                        "quotazione_usata": g.quotazione,
                        "spesa": g.spesa,
                    }
                    for g in new_giocatori
                ],
                extra={
                    "scadenza_contratto": scadenza.isoformat(),
                    "aumento_contestuale_totale": aumento_total,
                },
            )
            if aumento_op is not None:
                aumento_op.operation_snapshot = self._snapshot_json(
                    aumento_op,
                    fq_a_before=fq_before,
                    fq_a_after=fq_after,
                    conguaglio_da_before=fq_before,
                    conguaglio_da_after=fq_after,
                    giocatori_before={
                        g.id: asta_giocatori_after[g.id] for g in estendi_giocatori
                    },
                    giocatori_after=self._snapshot_map(estendi_giocatori),
                    giocatori_details=aumento_snapshot,
                    extra={"contestuale_ad_asta_operation_id": op.id},
                )
            undo.capture_after("fantasquadra", fq)
            undo.capture_after_many("giocatore", new_giocatori)
            undo.capture_after("operazione", op)
            if aumento_op is not None:
                undo.capture_after("operazione", aumento_op)
            undo.write(session, op.id)
            session.commit()

            session.expunge(op)
            return op

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    #  BUSINESS LOGIC — AUMENTO CONTRATTO                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def calcola_costo_aumento(giocatore) -> tuple:
        """
        Return (costo: int, anni_extra: int, nuova_scadenza: date) for a player.

        Rules based on data_acquisto month:
          jan / feb -> 30% of valore_svincolo, scadenza + 1 year
          aug / sep -> 35% of valore_svincolo, scadenza + 2 years
          all other months are not eligible for aumento contratto
        """
        vs    = float(giocatore.valore_svincolo or 0)
        month = giocatore.data_acquisto.month if giocatore.data_acquisto else 0

        if month in (1, 2):
            pct = 0.30
            anni_extra = 1
        elif month in (8, 9):
            pct = 0.35
            anni_extra = 2
        else:
            raise ValueError(
                "Aumento contratto consentito solo per giocatori acquistati "
                "a gennaio/febbraio o agosto/settembre."
            )

        costo = round(vs * pct)

        scad = giocatore.scadenza_contratto
        if scad:
            nuova_scadenza = scad.replace(year=scad.year + anni_extra)
        else:
            nuova_scadenza = datetime.date.today().replace(
                year=datetime.date.today().year + anni_extra, month=7, day=1
            )

        return costo, anni_extra, nuova_scadenza

    def calcola_aumento_contratto(
        self,
        fq_id: int,
        giocatore_ids: List[int],
        sessions_to_expire: Optional[List] = None,
    ) -> Operazione:
        """
        Execute an 'aumento contratto':
          - Compute cost per player (30% for Jan/Feb, 35% for Aug/Sep).
          - Raise ValueError if fq.fm < total cost.
          - Extend scadenza_contratto by 1 year for Jan/Feb, 2 years for Aug/Sep.
          - Deduct total cost from fq.fm.
          - Record one Operazione with per-player JSON snapshot.
        """
        for s in (sessions_to_expire or []):
            try:
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        session = self.session_factory()
        try:
            fq = session.query(Fantasquadra).filter_by(id=fq_id).one()
            giocatori = session.query(Giocatore).filter(
                Giocatore.id.in_(giocatore_ids)
            ).all()
            fq_before = model_snapshot(fq)
            giocatori_before = self._snapshot_map(giocatori)
            undo = SemanticUndoBuilder("aumento contratto")
            undo.capture_before("fantasquadra", fq)
            undo.capture_before_many("giocatore", giocatori)

            total_costo = 0
            snapshot_rows = []

            for g in giocatori:
                costo, anni_extra, nuova_scadenza = self.calcola_costo_aumento(g)
                total_costo += costo
                snapshot_rows.append({
                    "id":             g.id,
                    "nome":           g.nome,
                    "costo":          costo,
                    "nuova_scadenza": nuova_scadenza.isoformat(),
                    "anni_extra":     anni_extra,
                })
                g.scadenza_contratto = nuova_scadenza

            if fq.fm < total_costo:
                raise ValueError(
                    fq.nome + " non ha abbastanza FM per l'aumento contratto "
                    "(servono " + str(total_costo) + " FM, disponibili " + str(fq.fm) + " FM)."
                )

            fq.fm -= total_costo

            op = Operazione(
                fantasquadra_a_id  = fq_id,
                fantasquadra_b_id  = None,
                tipo_operazione    = "aumento contratto",
                conguaglio         = total_costo,
                conguaglio_da_id   = fq_id,
                data               = datetime.date.today().replace(day=1),
                clausole           = "",
            )
            op.giocatori = giocatori
            session.add(op)
            session.flush()
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_before,
                fq_a_after=model_snapshot(fq),
                conguaglio_da_before=fq_before,
                conguaglio_da_after=model_snapshot(fq),
                giocatori_before=giocatori_before,
                giocatori_after=self._snapshot_map(giocatori),
                giocatori_details=snapshot_rows,
            )
            undo.capture_after("fantasquadra", fq)
            undo.capture_after_many("giocatore", giocatori)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)
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
        sessions_to_expire: Optional[List] = None,   # pass Repository objects to release
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
        # Closing sibling sessions releases any open read transactions
        # (SQLite WAL: readers don't block writers, but pending flushes can).
        for s in (sessions_to_expire or []):
            try:
                # Accept both Repository objects and raw sessions
                session = s.session if hasattr(s, "session") else s
                session.close()
                if hasattr(s, "session_factory"):
                    s.session = s.session_factory()
            except Exception:
                pass

        # ── Open a dedicated session for this entire operation ───────────
        session = self.session_factory()
        try:
            # ── Resolve objects ──────────────────────────────────────────
            fq_venditrice = session.query(Fantasquadra).filter_by(id=fq_venditrice_id).one()
            fq_acquirente = session.query(Fantasquadra).filter_by(id=fq_acquirente_id).one()
            fq_venditrice_before = model_snapshot(fq_venditrice)
            fq_acquirente_before = model_snapshot(fq_acquirente)

            giocatore_ids = [d["id"] for d in giocatori_data]
            giocatori = (
                session.query(Giocatore)
                .filter(Giocatore.id.in_(giocatore_ids))
                .all()
            )
            giocatori_before = self._snapshot_map(giocatori)
            undo = SemanticUndoBuilder("acquisto definitivo")
            undo.capture_before("fantasquadra", fq_venditrice)
            undo.capture_before("fantasquadra", fq_acquirente)
            undo.capture_before_many("giocatore", giocatori)
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

                self._assign_team(g, fq_acquirente)
                self._clear_loan(g)
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
            session.flush()
            op.operation_snapshot = self._snapshot_json(
                op,
                fq_a_before=fq_venditrice_before,
                fq_a_after=model_snapshot(fq_venditrice),
                fq_b_before=fq_acquirente_before,
                fq_b_after=model_snapshot(fq_acquirente),
                conguaglio_da_before=fq_acquirente_before,
                conguaglio_da_after=model_snapshot(fq_acquirente),
                giocatori_before=giocatori_before,
                giocatori_after=self._snapshot_map(giocatori),
                giocatori_details=[
                    {
                        "id": g.id,
                        "quotazione_usata": quot_override[g.id],
                    }
                    for g in giocatori
                ],
                extra={"scadenza_contratto": scadenza.isoformat()},
            )
            undo.capture_after("fantasquadra", fq_venditrice)
            undo.capture_after("fantasquadra", fq_acquirente)
            undo.capture_after_many("giocatore", giocatori)
            undo.capture_after("operazione", op)
            undo.write(session, op.id)

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
