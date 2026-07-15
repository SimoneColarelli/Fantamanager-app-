from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import case, func

from models import Fantasquadra, Giocatore


@dataclass(frozen=True)
class TeamDashboardStats:
    id: int
    nome: str
    fm: int
    valore_rosa: int
    patrimonio: int
    in_rosa: int
    convocati: int


@dataclass(frozen=True)
class LoanInfo:
    giocatore: str
    from_team: str
    to_team: str
    inizio: dt.date | None
    fine: dt.date | None


@dataclass(frozen=True)
class ExpiringContractInfo:
    giocatore: str
    fantasquadra: str
    scadenza: dt.date


@dataclass(frozen=True)
class TeamExpiringContracts:
    fantasquadra: str
    contracts: list[ExpiringContractInfo]


@dataclass(frozen=True)
class LeagueTotals:
    fm: int
    valore_rose: int
    patrimonio: int
    giocatori_attivi: int
    prestiti_attivi: int
    contratti_in_scadenza: int


@dataclass(frozen=True)
class DashboardData:
    teams: list[TeamDashboardStats]
    loans: list[LoanInfo]
    expiring_contracts: list[ExpiringContractInfo]
    expiring_contract_groups: list[TeamExpiringContracts]
    totals: LeagueTotals
    top_fm: list[TeamDashboardStats]
    top_patrimonio: list[TeamDashboardStats]
    top_valore_rosa: list[TeamDashboardStats]


class DashboardService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def load_dashboard(self, today: dt.date | None = None) -> DashboardData:
        today = today or dt.date.today()
        one_year_from_today = today + dt.timedelta(days=365)
        session = self.session_factory()
        try:
            teams = self._team_stats(session)
            loans = self._active_loans(session)
            expiring = self._expiring_contracts(session, today, one_year_from_today)
            expiring_groups = self._expiring_contract_groups(teams, expiring)
            totals = LeagueTotals(
                fm=sum(team.fm for team in teams),
                valore_rose=sum(team.valore_rosa for team in teams),
                patrimonio=sum(team.patrimonio for team in teams),
                giocatori_attivi=sum(team.in_rosa for team in teams),
                prestiti_attivi=len(loans),
                contratti_in_scadenza=len(expiring),
            )
            return DashboardData(
                teams=teams,
                loans=loans,
                expiring_contracts=expiring,
                expiring_contract_groups=expiring_groups,
                totals=totals,
                top_fm=sorted(teams, key=lambda team: team.fm, reverse=True)[:5],
                top_patrimonio=sorted(
                    teams, key=lambda team: team.patrimonio, reverse=True
                )[:5],
                top_valore_rosa=sorted(
                    teams, key=lambda team: team.valore_rosa, reverse=True
                )[:5],
            )
        finally:
            session.close()

    def _team_stats(self, session) -> list[TeamDashboardStats]:
        raw_teams = (
            session.query(Fantasquadra.id, Fantasquadra.nome, Fantasquadra.fm)
            .filter(Fantasquadra.deleted == False)
            .order_by(Fantasquadra.nome)
            .all()
        )
        stats = {
            row.id: {
                "id": int(row.id),
                "nome": row.nome,
                "fm": int(row.fm or 0),
                "valore_rosa": 0,
                "patrimonio": int(row.fm or 0),
                "in_rosa": 0,
                "convocati": 0,
            }
            for row in raw_teams
        }

        effective_team_id = case(
            (
                Giocatore.prestito_a_fantasquadra_id.isnot(None),
                Giocatore.prestito_a_fantasquadra_id,
            ),
            else_=Giocatore.fantasquadra_id,
        )
        roster_rows = (
            session.query(
                effective_team_id.label("fantasquadra_id"),
                func.count(Giocatore.id),
                func.sum(case((Giocatore.convocato == True, 1), else_=0)),
            )
            .filter(
                Giocatore.deleted == False,
                Giocatore.in_serie_a == True,
                effective_team_id.isnot(None),
            )
            .group_by(effective_team_id)
            .all()
        )
        for fq_id, in_rosa, convocati in roster_rows:
            if fq_id in stats:
                stats[fq_id]["in_rosa"] = int(in_rosa or 0)
                stats[fq_id]["convocati"] = int(convocati or 0)

        value_rows = (
            session.query(Giocatore.fantasquadra_id, func.sum(Giocatore.valore_svincolo))
            .filter(
                Giocatore.deleted == False,
                Giocatore.fantasquadra_id.isnot(None),
            )
            .group_by(Giocatore.fantasquadra_id)
            .all()
        )
        for fq_id, valore_rosa in value_rows:
            if fq_id in stats:
                valore = int(valore_rosa or 0)
                stats[fq_id]["valore_rosa"] = valore
                stats[fq_id]["patrimonio"] = int(stats[fq_id]["fm"] + valore)

        return [TeamDashboardStats(**row) for row in stats.values()]

    def _active_loans(self, session) -> list[LoanInfo]:
        rows = (
            session.query(
                Giocatore.nome,
                Fantasquadra.nome.label("from_team"),
                Giocatore.in_prestito_a,
                Giocatore.inizio_prestito,
                Giocatore.fine_prestito,
            )
            .outerjoin(Fantasquadra, Giocatore.fantasquadra_id == Fantasquadra.id)
            .filter(
                Giocatore.deleted == False,
                Giocatore.in_prestito_a.isnot(None),
                Giocatore.in_prestito_a != "",
            )
            .order_by(Giocatore.fine_prestito, Giocatore.nome)
            .all()
        )
        return [
            LoanInfo(
                giocatore=row.nome,
                from_team=row.from_team or "-",
                to_team=row.in_prestito_a or "-",
                inizio=row.inizio_prestito,
                fine=row.fine_prestito,
            )
            for row in rows
        ]

    def _expiring_contracts(
        self,
        session,
        today: dt.date,
        one_year_from_today: dt.date,
    ) -> list[ExpiringContractInfo]:
        rows = (
            session.query(
                Giocatore.nome,
                Fantasquadra.nome.label("team_name"),
                Giocatore.scadenza_contratto,
            )
            .outerjoin(Fantasquadra, Giocatore.fantasquadra_id == Fantasquadra.id)
            .filter(
                Giocatore.deleted == False,
                Giocatore.in_serie_a == True,
                Giocatore.fantasquadra_id.isnot(None),
                Giocatore.scadenza_contratto.isnot(None),
                Giocatore.scadenza_contratto >= today,
                Giocatore.scadenza_contratto <= one_year_from_today,
            )
            .order_by(Giocatore.scadenza_contratto, Giocatore.nome)
            .all()
        )
        return [
            ExpiringContractInfo(
                giocatore=row.nome,
                fantasquadra=row.team_name or "-",
                scadenza=row.scadenza_contratto,
            )
            for row in rows
        ]

    def _expiring_contract_groups(
        self,
        teams: list[TeamDashboardStats],
        expiring_contracts: list[ExpiringContractInfo],
    ) -> list[TeamExpiringContracts]:
        by_team = {team.nome: [] for team in teams}
        for item in expiring_contracts:
            by_team.setdefault(item.fantasquadra, []).append(item)
        return [
            TeamExpiringContracts(fantasquadra=team.nome, contracts=by_team[team.nome])
            for team in teams
        ]
