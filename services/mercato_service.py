from __future__ import annotations

from typing import Callable

from operazione_repository import OperazioneRepository
from services.mercato_commands import (
    AcquistoDefinitivoCommand,
    AstaManualeCommand,
    AumentoContrattoCommand,
    ImportaAstaCommand,
    PrestitoCommand,
    RegistraOperazioneCommand,
    ScambioDefinitivoCommand,
    ScambioPrestitiCommand,
    SvincoloCommand,
)
from services.unit_of_work import UnitOfWork


class MercatoService:
    """Application service for mercato use cases."""

    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self.uow_factory = uow_factory

    @classmethod
    def from_repository(cls, repo: OperazioneRepository) -> "MercatoService":
        return cls(lambda: UnitOfWork(repo.session_factory, operazione_repo=repo))

    @staticmethod
    def _quote_payload(players):
        return [{"id": p.id, "quotazione": p.quotazione} for p in players]

    @staticmethod
    def _loan_payload(players):
        return [{"id": p.id, "fine_prestito": p.fine_prestito} for p in players]

    @staticmethod
    def _asta_payload(players):
        return [
            {
                "nome": p.nome,
                "quotazione": p.quotazione,
                "spesa": p.spesa,
                "estendi": p.estendi,
            }
            for p in players
        ]

    def registra_acquisto_definitivo(self, command: AcquistoDefinitivoCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_acquisto(
                giocatori_data=self._quote_payload(command.giocatori),
                fq_venditrice_id=command.fq_venditrice_id,
                fq_acquirente_id=command.fq_acquirente_id,
                fm=command.fm,
                data_acquisto=command.data_acquisto,
                clausole=command.clausole,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_scambio_definitivo(self, command: ScambioDefinitivoCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_scambio(
                giocatori_data_a=self._quote_payload(command.giocatori_a),
                giocatori_data_b=self._quote_payload(command.giocatori_b),
                fq_a_id=command.fq_a_id,
                fq_b_id=command.fq_b_id,
                fm=command.fm,
                data_acquisto=command.data_acquisto,
                clausole=command.clausole,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_prestito(self, command: PrestitoCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_prestito(
                giocatori_data=self._loan_payload(command.giocatori),
                fq_prestante_id=command.fq_prestante_id,
                fq_ricevente_id=command.fq_ricevente_id,
                fm=command.fm,
                inizio_prestito=command.inizio_prestito,
                clausole=command.clausole,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_scambio_prestiti(self, command: ScambioPrestitiCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_scambio_prestiti(
                giocatori_data_a=self._loan_payload(command.giocatori_a),
                giocatori_data_b=self._loan_payload(command.giocatori_b),
                fq_a_id=command.fq_a_id,
                fq_b_id=command.fq_b_id,
                fm=command.fm,
                inizio_prestito=command.inizio_prestito,
                clausole=command.clausole,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_svincolo(self, command: SvincoloCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_svincolo(
                giocatore_ids=command.giocatore_ids,
                fq_id=command.fq_id,
                data=command.data,
                clausole=command.clausole,
                sessions_to_expire=command.sessions_to_expire,
            )

    def importa_asta(self, command: ImportaAstaCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.importa_asta(
                asta_data=command.asta_data,
                data_asta=command.data_asta,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_asta_manuale(self, command: AstaManualeCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_asta_manuale(
                fq_id=command.fq_id,
                giocatori_data=self._asta_payload(command.giocatori),
                data_asta=command.data_asta,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_aumento_contratto(self, command: AumentoContrattoCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.calcola_aumento_contratto(
                fq_id=command.fq_id,
                giocatore_ids=command.giocatore_ids,
                sessions_to_expire=command.sessions_to_expire,
            )

    def registra_operazione_generica(self, command: RegistraOperazioneCommand):
        with self.uow_factory() as uow:
            return uow.operazioni.create(
                fantasquadra_a_id=command.fantasquadra_a_id,
                tipo_operazione=command.tipo_operazione,
                giocatore_ids=command.giocatore_ids,
                fantasquadra_b_id=command.fantasquadra_b_id,
                conguaglio=command.conguaglio,
                conguaglio_da_id=command.conguaglio_da_id,
                data=command.data,
                clausole=command.clausole,
            )
