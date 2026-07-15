import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Stagione, StagioneFase
from services.stagione_service import (
    ActiveStagioneExistsError,
    CreateStagioneCommand,
    FASE_1_ESTIVA,
    FASE_2_INVERNALE,
    FASE_3_FINE_STAGIONE,
    FASE_STATO_APERTA,
    FASE_STATO_PIANIFICATA,
    STAGIONE_STATO_ATTIVA,
    StagioneService,
    UpdateStagioneDatesCommand,
    UpdateStagioneFaseCommand,
    build_stagione_code,
    stagione_folder_name,
)


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_builds_stagione_code_and_storage_folder_name():
    assert build_stagione_code(2026) == "2026/2027"
    assert stagione_folder_name("2026/2027") == "2026-2027"


def test_create_stagione_creates_active_record_phases_and_storage(tmp_path):
    Session = _session_factory()
    storage_root = tmp_path / "Stagioni"
    service = StagioneService(Session, storage_root=storage_root)

    stagione = service.create_stagione(
        CreateStagioneCommand(
            anno_inizio=2026,
            data_inizio=dt.date(2026, 8, 1),
        )
    )

    assert stagione.codice == "2026/2027"
    assert stagione.anno_fine == 2027
    assert stagione.stato == STAGIONE_STATO_ATTIVA
    assert stagione.fase_corrente == FASE_1_ESTIVA
    assert stagione.storage_path == str(storage_root / "2026-2027")
    assert [fase.codice_fase for fase in stagione.fasi] == [
        FASE_1_ESTIVA,
        FASE_2_INVERNALE,
        FASE_3_FINE_STAGIONE,
    ]
    assert stagione.fasi[0].data_inizio == dt.date(2026, 8, 1)
    assert stagione.fasi[0].stato == FASE_STATO_APERTA
    assert stagione.fasi[1].stato == FASE_STATO_PIANIFICATA
    assert stagione.fasi[2].stato == FASE_STATO_PIANIFICATA

    expected_dirs = [
        storage_root / "2026-2027",
        storage_root / "2026-2027" / "01_fase_estiva" / "quotazioni",
        storage_root / "2026-2027" / "01_fase_estiva" / "backup",
        storage_root / "2026-2027" / "01_fase_estiva" / "asta",
        storage_root / "2026-2027" / "01_fase_estiva" / "report",
        storage_root / "2026-2027" / "02_fase_invernale" / "quotazioni",
        storage_root / "2026-2027" / "02_fase_invernale" / "backup",
        storage_root / "2026-2027" / "02_fase_invernale" / "asta",
        storage_root / "2026-2027" / "02_fase_invernale" / "report",
        storage_root / "2026-2027" / "03_fine_stagione" / "quotazioni",
        storage_root / "2026-2027" / "03_fine_stagione" / "backup",
        storage_root / "2026-2027" / "03_fine_stagione" / "report",
    ]
    for path in expected_dirs:
        assert path.is_dir()

    session = Session()
    try:
        assert session.query(Stagione).count() == 1
        assert session.query(StagioneFase).count() == 3
    finally:
        session.close()


def test_create_stagione_blocks_second_active_season(tmp_path):
    Session = _session_factory()
    service = StagioneService(Session, storage_root=tmp_path / "Stagioni")

    service.create_stagione(
        CreateStagioneCommand(
            anno_inizio=2026,
            data_inizio=dt.date(2026, 8, 1),
        )
    )

    with pytest.raises(ActiveStagioneExistsError):
        service.create_stagione(
            CreateStagioneCommand(
                anno_inizio=2027,
                data_inizio=dt.date(2027, 8, 1),
            )
        )


def test_update_stagione_dates_updates_phase_dates(tmp_path):
    Session = _session_factory()
    service = StagioneService(Session, storage_root=tmp_path / "Stagioni")
    stagione = service.create_stagione(
        CreateStagioneCommand(
            anno_inizio=2026,
            data_inizio=dt.date(2026, 8, 1),
        )
    )

    updated = service.update_stagione_dates(
        UpdateStagioneDatesCommand(
            stagione_id=stagione.id,
            data_inizio=dt.date(2026, 8, 5),
            data_fine=dt.date(2027, 6, 15),
            fasi=[
                UpdateStagioneFaseCommand(
                    codice_fase=FASE_1_ESTIVA,
                    data_inizio=dt.date(2026, 8, 5),
                    data_fine=dt.date(2026, 9, 10),
                    asta_data_inizio=dt.date(2026, 9, 1),
                    asta_data_fine=dt.date(2026, 9, 2),
                ),
                UpdateStagioneFaseCommand(
                    codice_fase=FASE_2_INVERNALE,
                    data_inizio=dt.date(2027, 1, 5),
                    data_fine=dt.date(2027, 2, 5),
                    asta_data_inizio=None,
                    asta_data_fine=None,
                ),
                UpdateStagioneFaseCommand(
                    codice_fase=FASE_3_FINE_STAGIONE,
                    data_inizio=dt.date(2027, 6, 1),
                    data_fine=dt.date(2027, 6, 15),
                    asta_data_inizio=None,
                    asta_data_fine=None,
                ),
            ],
        )
    )

    assert updated.data_inizio == dt.date(2026, 8, 5)
    assert updated.data_fine == dt.date(2027, 6, 15)
    phase_by_code = {fase.codice_fase: fase for fase in updated.fasi}
    assert phase_by_code[FASE_1_ESTIVA].data_fine == dt.date(2026, 9, 10)
    assert phase_by_code[FASE_1_ESTIVA].asta_data_inizio == dt.date(2026, 9, 1)
    assert phase_by_code[FASE_2_INVERNALE].data_inizio == dt.date(2027, 1, 5)
    assert phase_by_code[FASE_3_FINE_STAGIONE].data_fine == dt.date(2027, 6, 15)
