from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class PlayerQuoteCommand:
    id: int
    quotazione: int


@dataclass(frozen=True)
class PlayerLoanCommand:
    id: int
    fine_prestito: datetime.date


@dataclass(frozen=True)
class AstaPlayerCommand:
    nome: str
    quotazione: int
    spesa: int
    estendi: bool = False


@dataclass(frozen=True)
class AcquistoDefinitivoCommand:
    giocatori: List[PlayerQuoteCommand]
    fq_venditrice_id: int
    fq_acquirente_id: int
    fm: int
    data_acquisto: datetime.date
    clausole: Optional[str] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class ScambioDefinitivoCommand:
    giocatori_a: List[PlayerQuoteCommand]
    giocatori_b: List[PlayerQuoteCommand]
    fq_a_id: int
    fq_b_id: int
    fm: int = 0
    data_acquisto: datetime.date = field(default_factory=datetime.date.today)
    clausole: Optional[str] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class PrestitoCommand:
    giocatori: List[PlayerLoanCommand]
    fq_prestante_id: int
    fq_ricevente_id: int
    fm: int
    inizio_prestito: datetime.date
    clausole: Optional[str] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class ScambioPrestitiCommand:
    giocatori_a: List[PlayerLoanCommand]
    giocatori_b: List[PlayerLoanCommand]
    fq_a_id: int
    fq_b_id: int
    fm: int
    inizio_prestito: datetime.date
    clausole: Optional[str] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class SvincoloCommand:
    giocatore_ids: List[int]
    fq_id: int
    data: Optional[datetime.date] = None
    clausole: Optional[str] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class ImportaAstaCommand:
    asta_data: List[dict]
    data_asta: datetime.date
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class AstaManualeCommand:
    fq_id: int
    giocatori: List[AstaPlayerCommand]
    data_asta: Optional[datetime.date] = None
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class AumentoContrattoCommand:
    fq_id: int
    giocatore_ids: List[int]
    sessions_to_expire: Optional[List] = None


@dataclass(frozen=True)
class RegistraOperazioneCommand:
    fantasquadra_a_id: int
    tipo_operazione: str
    giocatore_ids: List[int]
    fantasquadra_b_id: Optional[int] = None
    conguaglio: int = 0
    conguaglio_da_id: Optional[int] = None
    data: Optional[datetime.date] = None
    clausole: Optional[str] = None
