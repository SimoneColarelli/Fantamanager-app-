from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from models import Stagione, StagioneFase


STAGIONE_STATO_ATTIVA = "attiva"
STAGIONE_STATO_CHIUSA = "chiusa"
FASE_STATO_APERTA = "aperta"
FASE_STATO_PIANIFICATA = "pianificata"

FASE_1_ESTIVA = "fase_1_estiva"
FASE_2_INVERNALE = "fase_2_invernale"
FASE_3_FINE_STAGIONE = "fase_3_fine_stagione"
FASE_CAMPIONATO_IN_CORSO = "campionato_in_corso"


@dataclass(frozen=True)
class PhaseDefinition:
    codice: str
    nome: str
    folder: str
    subfolders: tuple[str, ...]


PHASE_DEFINITIONS = (
    PhaseDefinition(
        codice=FASE_1_ESTIVA,
        nome="Inizio stagione - sessione mercato estiva",
        folder="01_fase_estiva",
        subfolders=("quotazioni", "backup", "asta", "report"),
    ),
    PhaseDefinition(
        codice=FASE_2_INVERNALE,
        nome="Sessione invernale di mercato",
        folder="02_fase_invernale",
        subfolders=("quotazioni", "backup", "asta", "report"),
    ),
    PhaseDefinition(
        codice=FASE_3_FINE_STAGIONE,
        nome="Fine stagione",
        folder="03_fine_stagione",
        subfolders=("quotazioni", "backup", "report"),
    ),
)


@dataclass(frozen=True)
class CreateStagioneCommand:
    anno_inizio: int
    data_inizio: dt.date
    codice: str | None = None


@dataclass(frozen=True)
class UpdateStagioneFaseCommand:
    codice_fase: str
    data_inizio: dt.date | None
    data_fine: dt.date | None
    asta_data_inizio: dt.date | None
    asta_data_fine: dt.date | None


@dataclass(frozen=True)
class UpdateStagioneDatesCommand:
    stagione_id: int
    data_inizio: dt.date
    data_fine: dt.date | None
    fasi: list[UpdateStagioneFaseCommand]


@dataclass(frozen=True)
class StagioneFaseDTO:
    id: int
    codice_fase: str
    nome: str
    data_inizio: dt.date | None
    data_fine: dt.date | None
    stato: str
    asta_data_inizio: dt.date | None
    asta_data_fine: dt.date | None


@dataclass(frozen=True)
class StagioneDTO:
    id: int
    codice: str
    anno_inizio: int
    anno_fine: int
    data_inizio: dt.date
    data_fine: dt.date | None
    stato: str
    fase_corrente: str | None
    storage_path: str
    fasi: list[StagioneFaseDTO]


class ActiveStagioneExistsError(RuntimeError):
    pass


class StagioneService:
    def __init__(self, session_factory, storage_root: str | Path = "Stagioni"):
        self.session_factory = session_factory
        self.storage_root = Path(storage_root)

    def create_stagione(self, command: CreateStagioneCommand) -> StagioneDTO:
        session = self.session_factory()
        try:
            active = self._active_stagione_query(session).first()
            if active:
                raise ActiveStagioneExistsError(
                    f"Esiste gia' una stagione attiva: {active.codice}"
                )

            codice = command.codice or build_stagione_code(command.anno_inizio)
            anno_fine = command.anno_inizio + 1
            storage_path = self.storage_root / stagione_folder_name(codice)
            now = dt.datetime.now()

            stagione = Stagione(
                codice=codice,
                anno_inizio=command.anno_inizio,
                anno_fine=anno_fine,
                data_inizio=command.data_inizio,
                stato=STAGIONE_STATO_ATTIVA,
                fase_corrente=FASE_1_ESTIVA,
                storage_path=str(storage_path),
                created_at=now,
                updated_at=now,
                deleted=False,
            )
            session.add(stagione)
            session.flush()

            for index, definition in enumerate(PHASE_DEFINITIONS):
                session.add(
                    StagioneFase(
                        stagione_id=stagione.id,
                        codice_fase=definition.codice,
                        nome=definition.nome,
                        data_inizio=command.data_inizio if index == 0 else None,
                        stato=(
                            FASE_STATO_APERTA
                            if index == 0
                            else FASE_STATO_PIANIFICATA
                        ),
                        created_at=now,
                        updated_at=now,
                    )
                )

            self.ensure_storage_dirs(storage_path)
            session.commit()
            session.refresh(stagione)
            return self._to_dto(stagione)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_active_stagione(self) -> StagioneDTO | None:
        session = self.session_factory()
        try:
            stagione = self._active_stagione_query(session).first()
            if not stagione:
                return None
            return self._to_dto(stagione)
        finally:
            session.close()

    def update_stagione_dates(
        self,
        command: UpdateStagioneDatesCommand,
    ) -> StagioneDTO:
        session = self.session_factory()
        try:
            stagione = (
                session.query(Stagione)
                .filter(Stagione.id == command.stagione_id, Stagione.deleted == False)
                .one()
            )
            now = dt.datetime.now()
            stagione.data_inizio = command.data_inizio
            stagione.data_fine = command.data_fine
            stagione.updated_at = now

            fasi_by_code = {fase.codice_fase: fase for fase in stagione.fasi}
            for phase_update in command.fasi:
                fase = fasi_by_code[phase_update.codice_fase]
                fase.data_inizio = phase_update.data_inizio
                fase.data_fine = phase_update.data_fine
                fase.asta_data_inizio = phase_update.asta_data_inizio
                fase.asta_data_fine = phase_update.asta_data_fine
                fase.updated_at = now

            session.commit()
            session.refresh(stagione)
            return self._to_dto(stagione)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ensure_storage_dirs(self, storage_path: Path) -> None:
        storage_path.mkdir(parents=True, exist_ok=True)
        for definition in PHASE_DEFINITIONS:
            phase_path = storage_path / definition.folder
            phase_path.mkdir(parents=True, exist_ok=True)
            for subfolder in definition.subfolders:
                (phase_path / subfolder).mkdir(parents=True, exist_ok=True)

    def _active_stagione_query(self, session):
        return session.query(Stagione).filter(
            Stagione.stato == STAGIONE_STATO_ATTIVA,
            Stagione.deleted == False,
        )

    def _to_dto(self, stagione: Stagione) -> StagioneDTO:
        fasi = sorted(stagione.fasi, key=lambda fase: fase.id or 0)
        return StagioneDTO(
            id=int(stagione.id),
            codice=stagione.codice,
            anno_inizio=int(stagione.anno_inizio),
            anno_fine=int(stagione.anno_fine),
            data_inizio=stagione.data_inizio,
            data_fine=stagione.data_fine,
            stato=stagione.stato,
            fase_corrente=stagione.fase_corrente,
            storage_path=stagione.storage_path,
            fasi=[
                StagioneFaseDTO(
                    id=int(fase.id),
                    codice_fase=fase.codice_fase,
                    nome=fase.nome,
                    data_inizio=fase.data_inizio,
                    data_fine=fase.data_fine,
                    stato=fase.stato,
                    asta_data_inizio=fase.asta_data_inizio,
                    asta_data_fine=fase.asta_data_fine,
                )
                for fase in fasi
            ],
        )


def build_stagione_code(anno_inizio: int) -> str:
    return f"{anno_inizio}/{anno_inizio + 1}"


def stagione_folder_name(codice: str) -> str:
    return codice.replace("/", "-").replace("\\", "-").strip()
