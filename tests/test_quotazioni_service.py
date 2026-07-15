from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Giocatore
from services.quotazioni_service import QuotazioniService


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_complete_update_updates_quote_dq_value_and_presence():
    Session = _session_factory()
    session = Session()
    try:
        session.add_all(
            [
                Giocatore(
                    nome="Present",
                    quotazione=10,
                    dq=0,
                    spesa=40,
                    valore_svincolo=40,
                    convocato=True,
                    in_serie_a=True,
                    deleted=False,
                ),
                Giocatore(
                    nome="Loaned",
                    quotazione=8,
                    dq=0,
                    spesa=30,
                    valore_svincolo=30,
                    in_prestito_a="Team B",
                    convocato=True,
                    in_serie_a=True,
                    deleted=False,
                ),
                Giocatore(
                    nome="Missing",
                    quotazione=5,
                    convocato=True,
                    in_serie_a=True,
                    deleted=False,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = QuotazioniService(Session).complete_update({"Present": 12, "Loaned": 9})

    session = Session()
    try:
        present = session.query(Giocatore).filter_by(nome="Present").one()
        loaned = session.query(Giocatore).filter_by(nome="Loaned").one()
        missing = session.query(Giocatore).filter_by(nome="Missing").one()

        assert result.total == 3
        assert result.presenti == 2
        assert result.assenti == 1
        assert result.quotazioni_aggiornate == 2
        assert result.valori_svincolo_aggiornati == 1
        assert present.quotazione == 12
        assert present.dq == 2
        assert present.valore_svincolo == 80
        assert loaned.quotazione == 9
        assert loaned.dq == 0
        assert loaned.valore_svincolo == 30
        assert missing.in_serie_a is False
        assert missing.convocato is False
    finally:
        session.close()


def test_quotazioni_update_does_not_recalculate_dq_or_value():
    Session = _session_factory()
    session = Session()
    try:
        session.add(
            Giocatore(
                nome="Present",
                quotazione=10,
                dq=1,
                spesa=40,
                valore_svincolo=62,
                convocato=True,
                in_serie_a=True,
                deleted=False,
            )
        )
        session.commit()
    finally:
        session.close()

    QuotazioniService(Session).quotazioni_update({"Present": 20})

    session = Session()
    try:
        player = session.query(Giocatore).filter_by(nome="Present").one()
        assert player.quotazione == 20
        assert player.dq == 1
        assert player.valore_svincolo == 62
    finally:
        session.close()


def test_calculate_update_value_uses_half_up_rounding():
    assert QuotazioniService.calculate_update_value(1, 40) == 62
