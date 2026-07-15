from __future__ import annotations

import math
from dataclasses import dataclass

from models import Giocatore


@dataclass(frozen=True)
class QuotazioniUpdateResult:
    total: int
    presenti: int
    assenti: int
    quotazioni_aggiornate: int
    valori_svincolo_aggiornati: int


class QuotazioniService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def complete_update(self, quotazioni: dict[str, int]) -> QuotazioniUpdateResult:
        return self._run_update(quotazioni, mode="complete")

    def quotazioni_update(self, quotazioni: dict[str, int]) -> QuotazioniUpdateResult:
        return self._run_update(quotazioni, mode="quotazioni")

    def serie_a_update(self, quotazioni: dict[str, int]) -> QuotazioniUpdateResult:
        return self._run_update(quotazioni, mode="serie_a")

    def _run_update(
        self,
        quotazioni: dict[str, int],
        mode: str,
    ) -> QuotazioniUpdateResult:
        session = self.session_factory()
        total = presenti = assenti = quote_updated = svincoli_updated = 0
        try:
            giocatori = session.query(Giocatore).all()
            total = len(giocatori)
            for giocatore in giocatori:
                if giocatore.nome not in quotazioni:
                    assenti += 1
                    giocatore.in_serie_a = False
                    giocatore.convocato = False
                    continue

                presenti += 1
                giocatore.in_serie_a = True

                if mode == "serie_a":
                    continue

                nuova_quotazione = int(quotazioni[giocatore.nome])
                vecchia_quotazione = int(giocatore.quotazione or 0)
                partial_dq = nuova_quotazione - vecchia_quotazione
                giocatore.quotazione = nuova_quotazione
                quote_updated += 1

                if mode == "complete" and not giocatore.in_prestito_a:
                    valore_dq_attuale = int(giocatore.dq or 0)
                    giocatore.dq = valore_dq_attuale + partial_dq
                    spesa = int(giocatore.spesa or 1)
                    giocatore.valore_svincolo = self.calculate_update_value(
                        giocatore.dq,
                        spesa,
                    )
                    svincoli_updated += 1

            session.commit()
            return QuotazioniUpdateResult(
                total=total,
                presenti=presenti,
                assenti=assenti,
                quotazioni_aggiornate=quote_updated,
                valori_svincolo_aggiornati=svincoli_updated,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def calculate_update_value(dq, spesa) -> int:
        new_current_value = spesa if spesa is not None else 0
        dq = dq if dq is not None else 0
        delta_abs = abs(dq)
        delta_sign = 1 if dq > 0 else -1

        if dq == 0:
            return _round_half_up(new_current_value)

        for _ in range(delta_abs, 0, -1):
            if 1 <= new_current_value <= 49:
                if delta_sign == -1:
                    new_current_value = new_current_value - 3 * delta_abs
                    break
                new_current_value += 21.5
            elif 50 <= new_current_value <= 99:
                if delta_sign == -1:
                    new_current_value = new_current_value - 8 * delta_abs
                    break
                new_current_value += 18
            elif 100 <= new_current_value <= 199:
                if delta_sign == -1:
                    new_current_value = new_current_value - 12 * delta_abs
                    break
                new_current_value += 12
            elif 200 <= new_current_value <= 399:
                if delta_sign == -1:
                    new_current_value = new_current_value - 18 * delta_abs
                    break
                new_current_value += 8
            elif 400 <= new_current_value <= 599:
                if delta_sign == -1:
                    new_current_value = new_current_value - 21.5 * delta_abs
                    break
                new_current_value += 3
            elif 600 <= new_current_value <= 99999:
                if delta_sign == -1:
                    new_current_value = new_current_value - 30 * delta_abs
                    break
                new_current_value += 1

        return _round_half_up(new_current_value if new_current_value > 0 else 1)


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))
