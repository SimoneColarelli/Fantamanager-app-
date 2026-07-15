import datetime as dt
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Fantasquadra, Giocatore, Operazione, StagioneFile
from services.backup_service import BackupService
from services.stagione_service import CreateStagioneCommand, StagioneService


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_market_data(Session):
    session = Session()
    try:
        team = Fantasquadra(id=1, nome="Team A", fm=100, deleted=False)
        player = Giocatore(
            id=10,
            nome="Player A",
            squadra="Team A",
            fantasquadra_id=1,
            valore_svincolo=20,
            convocato=True,
            in_serie_a=True,
            deleted=False,
        )
        operation = Operazione(
            id=20,
            fantasquadra_a_id=1,
            tipo_operazione="asta",
            conguaglio=0,
            data=dt.date(2026, 8, 1),
        )
        operation.giocatori = [player]
        session.add_all([team, player, operation])
        session.commit()
    finally:
        session.close()


def test_export_tables_to_file_writes_requested_tables(tmp_path):
    Session = _session_factory()
    _seed_market_data(Session)

    path = BackupService(Session).export_tables_to_file(
        ("giocatori", "fantasquadre"),
        tmp_path / "backup.json",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"giocatori", "fantasquadre"}
    assert payload["giocatori"][0]["nome"] == "Player A"
    assert payload["fantasquadre"][0]["nome"] == "Team A"


def test_create_season_backup_writes_files_and_registers_them(tmp_path):
    Session = _session_factory()
    _seed_market_data(Session)
    stagione = StagioneService(Session, storage_root=tmp_path / "Stagioni").create_stagione(
        CreateStagioneCommand(
            anno_inizio=2026,
            data_inizio=dt.date(2026, 8, 1),
        )
    )

    result = BackupService(Session).create_season_backup(stagione, "inizio_stagione")

    assert result.ok
    assert len(result.paths) == 2
    for path in result.paths:
        assert path.is_file()
        assert path.parent == tmp_path / "Stagioni" / "2026-2027" / "01_fase_estiva" / "backup"

    session = Session()
    try:
        files = session.query(StagioneFile).order_by(StagioneFile.tipo_file).all()
        assert [file.tipo_file for file in files] == [
            "backup_fantasquadre",
            "backup_giocatori",
        ]
        assert all(file.fase_id is not None for file in files)
        assert all(file.note == "inizio_stagione" for file in files)
    finally:
        session.close()


def test_export_rosters_for_asta_writes_json_and_registers_file(tmp_path):
    Session = _session_factory()
    _seed_market_data(Session)
    stagione = StagioneService(Session, storage_root=tmp_path / "Stagioni").create_stagione(
        CreateStagioneCommand(
            anno_inizio=2026,
            data_inizio=dt.date(2026, 8, 1),
        )
    )

    result = BackupService(Session).export_rosters_for_asta(
        stagione,
        "fase_1_estiva",
    )

    assert result.ok
    path = result.paths[0]
    assert path.is_file()
    assert path.parent == tmp_path / "Stagioni" / "2026-2027" / "01_fase_estiva" / "asta"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["tipo"] == "export_rosters_for_asta"
    assert payload["squadre"][0]["nome"] == "Team A"
    assert payload["squadre"][0]["giocatori"][0]["nome"] == "Player A"

    session = Session()
    try:
        file = session.query(StagioneFile).filter_by(tipo_file="export_asta").one()
        assert file.fase_id is not None
        assert file.note == "export_rosters_for_asta"
    finally:
        session.close()
