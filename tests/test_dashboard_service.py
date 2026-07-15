import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Fantasquadra, Giocatore
from services.dashboard_service import DashboardService


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_dashboard_aggregates_team_cards_loans_and_expiring_contracts():
    Session = _session_factory()
    session = Session()
    today = dt.date(2026, 7, 15)
    try:
        team_a = Fantasquadra(nome="Team A", fm=100)
        team_b = Fantasquadra(nome="Team B", fm=200)
        session.add_all([team_a, team_b])
        session.flush()

        session.add_all(
            [
                Giocatore(
                    nome="Owner Starter",
                    squadra=team_a.nome,
                    fantasquadra_id=team_a.id,
                    valore_svincolo=50,
                    scadenza_contratto=today + dt.timedelta(days=100),
                    convocato=True,
                    in_serie_a=True,
                    deleted=False,
                ),
                Giocatore(
                    nome="Loaned Player",
                    squadra=team_a.nome,
                    fantasquadra_id=team_a.id,
                    valore_svincolo=70,
                    in_prestito_a=team_b.nome,
                    prestito_a_fantasquadra_id=team_b.id,
                    inizio_prestito=today,
                    fine_prestito=today + dt.timedelta(days=180),
                    convocato=False,
                    in_serie_a=True,
                    deleted=False,
                ),
                Giocatore(
                    nome="Remote Starter",
                    squadra=team_b.nome,
                    fantasquadra_id=team_b.id,
                    valore_svincolo=30,
                    scadenza_contratto=today + dt.timedelta(days=500),
                    convocato=True,
                    in_serie_a=True,
                    deleted=False,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    dashboard = DashboardService(Session).load_dashboard(today=today)
    teams = {team.nome: team for team in dashboard.teams}

    assert teams["Team A"].fm == 100
    assert teams["Team A"].valore_rosa == 120
    assert teams["Team A"].patrimonio == 220
    assert teams["Team A"].in_rosa == 1
    assert teams["Team A"].convocati == 1

    assert teams["Team B"].fm == 200
    assert teams["Team B"].valore_rosa == 30
    assert teams["Team B"].patrimonio == 230
    assert teams["Team B"].in_rosa == 2
    assert teams["Team B"].convocati == 1

    assert dashboard.top_fm[0].nome == "Team B"
    assert dashboard.loans[0].giocatore == "Loaned Player"
    assert dashboard.loans[0].from_team == "Team A"
    assert dashboard.loans[0].to_team == "Team B"
    assert [item.giocatore for item in dashboard.expiring_contracts] == ["Owner Starter"]

    expiring_by_team = {
        group.fantasquadra: [item.giocatore for item in group.contracts]
        for group in dashboard.expiring_contract_groups
    }
    assert expiring_by_team == {
        "Team A": ["Owner Starter"],
        "Team B": [],
    }
