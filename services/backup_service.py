from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import inspect, text

from database import Base
from models import Fantasquadra, Giocatore, StagioneFase, StagioneFile, operazione_giocatori
from services.stagione_service import PHASE_DEFINITIONS, StagioneDTO


@dataclass(frozen=True)
class BackupResult:
    ok: bool
    message: str
    paths: list[Path]


@dataclass(frozen=True)
class SeasonalBackupFile:
    label: str
    table_names: tuple[str, ...]


@dataclass(frozen=True)
class SeasonalBackupDefinition:
    key: str
    phase_code: str
    label: str
    files: tuple[SeasonalBackupFile, ...]


def _seasonal_files(prefix: str) -> tuple[SeasonalBackupFile, ...]:
    return (
        SeasonalBackupFile(label=f"Giocatori {prefix}", table_names=("giocatori",)),
        SeasonalBackupFile(label=f"Fantasquadre {prefix}", table_names=("fantasquadre",)),
    )


def _seasonal_files_with_operations(prefix: str) -> tuple[SeasonalBackupFile, ...]:
    return _seasonal_files(prefix) + (
        SeasonalBackupFile(
            label=f"Operazioni {prefix}",
            table_names=("operazioni", "operazione_giocatori"),
        ),
    )


SEASONAL_BACKUPS = {
    "inizio_stagione": SeasonalBackupDefinition(
        key="inizio_stagione",
        phase_code="fase_1_estiva",
        label="Backup inizio stagione",
        files=_seasonal_files("inizio stagione"),
    ),
    "pre_asta_estiva": SeasonalBackupDefinition(
        key="pre_asta_estiva",
        phase_code="fase_1_estiva",
        label="Backup pre asta estiva",
        files=_seasonal_files("pre asta estiva"),
    ),
    "post_asta_estiva": SeasonalBackupDefinition(
        key="post_asta_estiva",
        phase_code="fase_1_estiva",
        label="Backup post asta estiva",
        files=_seasonal_files("post asta estiva"),
    ),
    "chiusura_sessione_estiva": SeasonalBackupDefinition(
        key="chiusura_sessione_estiva",
        phase_code="fase_1_estiva",
        label="Backup chiusura sessione estiva",
        files=_seasonal_files_with_operations("chiusura sessione estiva"),
    ),
    "inizio_sessione_invernale": SeasonalBackupDefinition(
        key="inizio_sessione_invernale",
        phase_code="fase_2_invernale",
        label="Backup inizio sessione invernale",
        files=_seasonal_files("inizio sessione invernale"),
    ),
    "pre_asta_invernale": SeasonalBackupDefinition(
        key="pre_asta_invernale",
        phase_code="fase_2_invernale",
        label="Backup pre asta invernale",
        files=_seasonal_files("pre asta invernale"),
    ),
    "post_asta_invernale": SeasonalBackupDefinition(
        key="post_asta_invernale",
        phase_code="fase_2_invernale",
        label="Backup post asta invernale",
        files=_seasonal_files("post asta invernale"),
    ),
    "chiusura_sessione_invernale": SeasonalBackupDefinition(
        key="chiusura_sessione_invernale",
        phase_code="fase_2_invernale",
        label="Backup chiusura sessione invernale",
        files=_seasonal_files_with_operations("chiusura sessione invernale"),
    ),
    "fine_stagione": SeasonalBackupDefinition(
        key="fine_stagione",
        phase_code="fase_3_fine_stagione",
        label="Backup fine stagione",
        files=_seasonal_files_with_operations("fine stagione"),
    ),
}


class BackupService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def get_all_models():
        return [mapper.class_ for mapper in Base.registry.mappers]

    @staticmethod
    def model_to_dict(obj) -> dict:
        data = {}
        mapper = inspect(obj).mapper
        for col in mapper.column_attrs:
            value = getattr(obj, col.key)
            if isinstance(value, (dt.date, dt.datetime)):
                value = value.isoformat()
            data[col.key] = value
        return data

    def export_data(self, filepath: str | Path, models: Iterable[type] | None = None):
        target_models = list(models) if models else self.get_all_models()
        table_names = [model.__tablename__ for model in target_models]
        if "operazione_giocatori" not in table_names:
            table_names.append("operazione_giocatori")
        self.export_tables_to_file(table_names, filepath)
        return True, "Backup creato correttamente."

    def export_tables_to_file(
        self,
        table_names: Iterable[str],
        filepath: str | Path,
    ) -> Path:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        session = self.session_factory()
        try:
            payload = {
                table_name: self._read_table(session, table_name)
                for table_name in table_names
            }
            filepath.write_text(
                json.dumps(payload, indent=4, ensure_ascii=False),
                encoding="utf-8",
            )
            return filepath
        finally:
            session.close()

    def create_season_backup(
        self,
        stagione: StagioneDTO,
        backup_key: str,
    ) -> BackupResult:
        definition = SEASONAL_BACKUPS[backup_key]
        phase_folder = self._phase_folder(definition.phase_code)
        backup_dir = Path(stagione.storage_path) / phase_folder / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        season_suffix = stagione.codice.replace("/", "-").replace("\\", "-")
        created_files: list[tuple[SeasonalBackupFile, Path]] = []
        for file_def in definition.files:
            filepath = backup_dir / f"{file_def.label} {season_suffix}.json"
            created_files.append(
                (file_def, self.export_tables_to_file(file_def.table_names, filepath))
            )

        self._record_season_files(stagione, definition, created_files)

        return BackupResult(
            ok=True,
            message=f"{definition.label} creato correttamente.",
            paths=[path for _, path in created_files],
        )

    def export_rosters_for_asta(
        self,
        stagione: StagioneDTO,
        phase_code: str,
    ) -> BackupResult:
        label = (
            "Rose per asta estiva"
            if phase_code == "fase_1_estiva"
            else "Rose per asta invernale"
        )
        phase_folder = self._phase_folder(phase_code)
        asta_dir = Path(stagione.storage_path) / phase_folder / "asta"
        asta_dir.mkdir(parents=True, exist_ok=True)
        season_suffix = stagione.codice.replace("/", "-").replace("\\", "-")
        filepath = asta_dir / f"{label} {season_suffix}.json"

        payload = self._rosters_payload(stagione, phase_code)
        filepath.write_text(
            json.dumps(payload, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        self._record_file(
            stagione=stagione,
            phase_code=phase_code,
            tipo_file="export_asta",
            nome_logico=f"{label} {stagione.codice}",
            path=filepath,
            note="export_rosters_for_asta",
        )
        return BackupResult(
            ok=True,
            message=f"{label} esportate correttamente.",
            paths=[filepath],
        )

    def _read_table(self, session, table_name: str) -> list[dict]:
        if table_name == operazione_giocatori.name:
            rows = session.execute(
                text("SELECT operazione_id, giocatore_id FROM operazione_giocatori")
            ).fetchall()
            return [
                {"operazione_id": row[0], "giocatore_id": row[1]}
                for row in rows
            ]

        model = self._model_by_table_name()[table_name]
        return [self.model_to_dict(row) for row in session.query(model).all()]

    def _model_by_table_name(self) -> dict[str, type]:
        return {model.__tablename__: model for model in self.get_all_models()}

    def _phase_folder(self, phase_code: str) -> str:
        return next(
            definition.folder
            for definition in PHASE_DEFINITIONS
            if definition.codice == phase_code
        )

    def _rosters_payload(self, stagione: StagioneDTO, phase_code: str) -> dict:
        session = self.session_factory()
        try:
            teams = (
                session.query(Fantasquadra)
                .filter(Fantasquadra.deleted.is_(False))
                .order_by(Fantasquadra.nome)
                .all()
            )
            payload_teams = []
            for team in teams:
                players = (
                    session.query(Giocatore)
                    .filter(
                        Giocatore.deleted.is_(False),
                        Giocatore.fantasquadra_id == team.id,
                    )
                    .order_by(Giocatore.nome)
                    .all()
                )
                payload_teams.append(
                    {
                        "id": team.id,
                        "nome": team.nome,
                        "fm": team.fm,
                        "giocatori": [
                            {
                                "id": player.id,
                                "nome": player.nome,
                                "squadra": player.squadra,
                                "quotazione": player.quotazione,
                                "valore_svincolo": player.valore_svincolo,
                                "scadenza_contratto": player.scadenza_contratto.isoformat()
                                if player.scadenza_contratto
                                else None,
                                "in_prestito_a": player.in_prestito_a,
                                "convocato": player.convocato,
                                "in_serie_a": player.in_serie_a,
                            }
                            for player in players
                        ],
                    }
                )
            return {
                "schema_version": 1,
                "tipo": "export_rosters_for_asta",
                "stagione": stagione.codice,
                "fase": phase_code,
                "generated_at": dt.datetime.now().isoformat(),
                "squadre": payload_teams,
            }
        finally:
            session.close()

    def _record_season_files(
        self,
        stagione: StagioneDTO,
        definition: SeasonalBackupDefinition,
        created_files: list[tuple[SeasonalBackupFile, Path]],
    ) -> None:
        session = self.session_factory()
        try:
            fase = (
                session.query(StagioneFase)
                .filter(
                    StagioneFase.stagione_id == stagione.id,
                    StagioneFase.codice_fase == definition.phase_code,
                )
                .one_or_none()
            )
            now = dt.datetime.now()
            for file_def, path in created_files:
                session.add(
                    StagioneFile(
                        stagione_id=stagione.id,
                        fase_id=fase.id if fase else None,
                        tipo_file=self._file_type(file_def),
                        nome_logico=f"{file_def.label} {stagione.codice}",
                        path=str(path),
                        created_at=now,
                        note=definition.key,
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _record_file(
        self,
        stagione: StagioneDTO,
        phase_code: str,
        tipo_file: str,
        nome_logico: str,
        path: Path,
        note: str | None = None,
    ) -> None:
        session = self.session_factory()
        try:
            fase = (
                session.query(StagioneFase)
                .filter(
                    StagioneFase.stagione_id == stagione.id,
                    StagioneFase.codice_fase == phase_code,
                )
                .one_or_none()
            )
            session.add(
                StagioneFile(
                    stagione_id=stagione.id,
                    fase_id=fase.id if fase else None,
                    tipo_file=tipo_file,
                    nome_logico=nome_logico,
                    path=str(path),
                    created_at=dt.datetime.now(),
                    note=note,
                )
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _file_type(self, file_def: SeasonalBackupFile) -> str:
        if file_def.table_names == ("giocatori",):
            return "backup_giocatori"
        if file_def.table_names == ("fantasquadre",):
            return "backup_fantasquadre"
        if "operazioni" in file_def.table_names:
            return "backup_operazioni"
        return "backup"
