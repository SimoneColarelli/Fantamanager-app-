import datetime
import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from migration_runner import run_migrations
from models import Fantasquadra, Giocatore, Operazione
from operazione_repository import OperazioneRepository
from services.mercato_commands import (
    AcquistoDefinitivoCommand,
    AstaManualeCommand,
    AstaPlayerCommand,
    PlayerQuoteCommand,
    SvincoloCommand,
)
from services.mercato_service import MercatoService


class BusinessRuleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        run_migrations(self.engine)
        self.Session = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.repo = OperazioneRepository(self.Session)
        self.service = MercatoService.from_repository(self.repo)

    def tearDown(self):
        try:
            self.repo.session.close()
        finally:
            Base.metadata.drop_all(self.engine)
            self.engine.dispose()

    def seed_team(self, nome="Team A", fm=1000):
        session = self.Session()
        try:
            team = Fantasquadra(nome=nome, fm=fm, deleted=False)
            session.add(team)
            session.commit()
            team_id = team.id
            return team_id
        finally:
            session.close()

    def seed_player(
        self,
        nome="Player",
        squadra="Team A",
        spesa=100,
        quotazione=10,
        valore_svincolo=100,
        data_acquisto=datetime.date(2026, 8, 1),
        scadenza=datetime.date(2029, 7, 1),
    ):
        session = self.Session()
        try:
            player = Giocatore(
                nome=nome,
                squadra=squadra,
                spesa=spesa,
                data_acquisto=data_acquisto,
                fascia="3",
                quotazione=quotazione,
                dq=0,
                valore_svincolo=valore_svincolo,
                scadenza_contratto=scadenza,
                convocato=True,
                in_serie_a=True,
                deleted=False,
            )
            session.add(player)
            session.commit()
            player_id = player.id
            return player_id
        finally:
            session.close()

    def test_calcola_costo_aumento_allowed_months_and_blocked_month(self):
        jan = SimpleNamespace(
            valore_svincolo=333,
            data_acquisto=datetime.date(2026, 1, 1),
            scadenza_contratto=datetime.date(2026, 7, 1),
        )
        aug = SimpleNamespace(
            valore_svincolo=333,
            data_acquisto=datetime.date(2026, 8, 1),
            scadenza_contratto=datetime.date(2026, 7, 1),
        )
        mar = SimpleNamespace(
            valore_svincolo=333,
            data_acquisto=datetime.date(2026, 3, 1),
            scadenza_contratto=datetime.date(2026, 7, 1),
        )

        self.assertEqual(
            self.repo.calcola_costo_aumento(jan),
            (100, 1, datetime.date(2027, 7, 1)),
        )
        self.assertEqual(
            self.repo.calcola_costo_aumento(aug),
            (117, 2, datetime.date(2028, 7, 1)),
        )
        with self.assertRaises(ValueError):
            self.repo.calcola_costo_aumento(mar)

    def test_asta_manuale_with_estensione_creates_aumento_and_updates_fm(self):
        team_id = self.seed_team("Team A", fm=1000)

        self.service.registra_asta_manuale(
            AstaManualeCommand(
                fq_id=team_id,
                giocatori=[
                    AstaPlayerCommand(
                        nome="Asta Player",
                        quotazione=10,
                        spesa=100,
                        estendi=True,
                    )
                ],
                data_asta=datetime.date(2026, 8, 1),
            )
        )

        session = self.Session()
        try:
            team = session.query(Fantasquadra).filter_by(id=team_id).one()
            player = session.query(Giocatore).filter_by(nome="Asta Player").one()
            ops = session.query(Operazione).order_by(Operazione.id).all()

            self.assertEqual(team.fm, 865)
            self.assertEqual(player.fantasquadra_id, team_id)
            self.assertIsNone(player.prestito_a_fantasquadra_id)
            self.assertEqual(player.scadenza_contratto, datetime.date(2031, 7, 1))
            self.assertEqual([op.tipo_operazione for op in ops], ["asta", "aumento contratto"])
            self.assertEqual(ops[0].conguaglio, 100)
            self.assertEqual(ops[1].conguaglio, 35)
        finally:
            session.close()

    def test_acquisto_definitivo_updates_player_and_balances(self):
        seller_id = self.seed_team("Seller", fm=0)
        buyer_id = self.seed_team("Buyer", fm=1000)
        player_id = self.seed_player(
            nome="Sold Player",
            squadra="Seller",
            valore_svincolo=100,
            data_acquisto=datetime.date(2025, 8, 1),
            scadenza=datetime.date(2028, 7, 1),
        )

        self.service.registra_acquisto_definitivo(
            AcquistoDefinitivoCommand(
                giocatori=[PlayerQuoteCommand(id=player_id, quotazione=10)],
                fq_venditrice_id=seller_id,
                fq_acquirente_id=buyer_id,
                fm=200,
                data_acquisto=datetime.date(2026, 1, 15),
            )
        )

        session = self.Session()
        try:
            seller = session.query(Fantasquadra).filter_by(id=seller_id).one()
            buyer = session.query(Fantasquadra).filter_by(id=buyer_id).one()
            player = session.query(Giocatore).filter_by(id=player_id).one()

            self.assertEqual(seller.fm, 200)
            self.assertEqual(buyer.fm, 800)
            self.assertEqual(player.squadra, "Buyer")
            self.assertEqual(player.fantasquadra_id, buyer_id)
            self.assertIsNone(player.in_prestito_a)
            self.assertIsNone(player.prestito_a_fantasquadra_id)
            self.assertEqual(player.spesa, 200)
            self.assertEqual(player.valore_svincolo, 200)
            self.assertEqual(player.scadenza_contratto, datetime.date(2028, 7, 1))
            self.assertFalse(player.convocato)
        finally:
            session.close()

    def test_svincolo_credits_fm_and_removes_player(self):
        team_id = self.seed_team("Team A", fm=100)
        player_id = self.seed_player(nome="Released", squadra="Team A", valore_svincolo=75)

        self.service.registra_svincolo(
            SvincoloCommand(
                giocatore_ids=[player_id],
                fq_id=team_id,
                data=datetime.date(2026, 8, 1),
            )
        )

        session = self.Session()
        try:
            team = session.query(Fantasquadra).filter_by(id=team_id).one()
            player_count = session.query(Giocatore).filter_by(id=player_id).count()
            op = session.query(Operazione).filter_by(tipo_operazione="svincolo").one()

            self.assertEqual(team.fm, 175)
            self.assertEqual(player_count, 0)
            snapshot = json.loads(op.operation_snapshot)
            self.assertEqual(snapshot["tipo_operazione"], "svincolo")
            self.assertIn("Released", op.operation_snapshot)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
