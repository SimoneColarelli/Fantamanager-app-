import datetime
import json
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base
from migration_runner import run_migrations
from models import Fantasquadra, Giocatore, TIPI_OPERAZIONE
from operazione_repository import OperazioneRepository
from persistence.semantic_undo import (
    INVERSE_OPERATION_DEFINITIONS,
    SemanticUndoConflict,
    inverse_definition_for,
    list_undoable_transactions,
    undo_transaction,
)
from services.mercato_commands import (
    AcquistoDefinitivoCommand,
    AstaManualeCommand,
    AstaPlayerCommand,
    AumentoContrattoCommand,
    ImportaAstaCommand,
    PlayerQuoteCommand,
    PlayerLoanCommand,
    PrestitoCommand,
    ScambioDefinitivoCommand,
    ScambioPrestitiCommand,
    SvincoloCommand,
)
from services.mercato_service import MercatoService


class SemanticUndoTests(unittest.TestCase):
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

    def seed_team(self, nome, fm):
        session = self.Session()
        try:
            team = Fantasquadra(nome=nome, fm=fm, deleted=False)
            session.add(team)
            session.commit()
            return team.id
        finally:
            session.close()

    def seed_player(self, nome, squadra, valore_svincolo=100):
        session = self.Session()
        try:
            player = Giocatore(
                nome=nome,
                squadra=squadra,
                spesa=valore_svincolo,
                data_acquisto=datetime.date(2026, 1, 1),
                fascia="3",
                quotazione=10,
                dq=0,
                valore_svincolo=valore_svincolo,
                scadenza_contratto=datetime.date(2028, 7, 1),
                convocato=True,
                in_serie_a=True,
                deleted=False,
            )
            session.add(player)
            session.commit()
            return player.id
        finally:
            session.close()

    def semantic_rows(self):
        session = self.Session()
        try:
            return session.execute(
                text(
                    """
                    SELECT transaction_id, operation_id, operation_type,
                           inverse_action_type, entity_type, entity_id,
                           before_snapshot, after_snapshot, inverse_payload,
                           status
                    FROM semantic_undo_log
                    ORDER BY id
                    """
                )
            ).mappings().all()
        finally:
            session.close()

    def operation_types_in_audit(self):
        return {row["operation_type"] for row in self.semantic_rows()}

    def latest_transaction_id(self):
        transactions = list_undoable_transactions(self.Session)
        self.assertGreaterEqual(len(transactions), 1)
        return transactions[0].transaction_id

    def test_every_market_operation_has_inverse_definition(self):
        self.assertEqual(
            sorted(INVERSE_OPERATION_DEFINITIONS.keys()),
            sorted(TIPI_OPERAZIONE),
        )
        for operation_type in TIPI_OPERAZIONE:
            definition = inverse_definition_for(operation_type)
            self.assertTrue(definition["inverse_action_type"].startswith("undo_"))
            self.assertTrue(definition["description"])

    def test_acquisto_definitivo_records_before_after_audit(self):
        seller_id = self.seed_team("Seller", 0)
        buyer_id = self.seed_team("Buyer", 1000)
        player_id = self.seed_player("Sold Player", "Seller", valore_svincolo=100)

        self.service.registra_acquisto_definitivo(
            AcquistoDefinitivoCommand(
                giocatori=[PlayerQuoteCommand(id=player_id, quotazione=10)],
                fq_venditrice_id=seller_id,
                fq_acquirente_id=buyer_id,
                fm=200,
                data_acquisto=datetime.date(2026, 1, 1),
            )
        )

        rows = self.semantic_rows()
        self.assertEqual({row["operation_type"] for row in rows}, {"acquisto definitivo"})
        self.assertEqual(
            {row["inverse_action_type"] for row in rows},
            {"undo_acquisto_definitivo"},
        )
        self.assertEqual(len({row["transaction_id"] for row in rows}), 1)
        self.assertEqual(
            {row["entity_type"] for row in rows},
            {"fantasquadra", "giocatore", "operazione"},
        )

        player_row = next(row for row in rows if row["entity_type"] == "giocatore")
        before = json.loads(player_row["before_snapshot"])
        after = json.loads(player_row["after_snapshot"])
        self.assertEqual(before["squadra"], "Seller")
        self.assertEqual(after["squadra"], "Buyer")

    def test_undo_acquisto_definitivo_restores_domain_state(self):
        seller_id = self.seed_team("Seller", 0)
        buyer_id = self.seed_team("Buyer", 1000)
        player_id = self.seed_player("Sold Player", "Seller", valore_svincolo=100)

        self.service.registra_acquisto_definitivo(
            AcquistoDefinitivoCommand(
                giocatori=[PlayerQuoteCommand(id=player_id, quotazione=10)],
                fq_venditrice_id=seller_id,
                fq_acquirente_id=buyer_id,
                fm=200,
                data_acquisto=datetime.date(2026, 1, 1),
            )
        )

        result = undo_transaction(self.Session, self.latest_transaction_id())

        session = self.Session()
        try:
            seller = session.get(Fantasquadra, seller_id)
            buyer = session.get(Fantasquadra, buyer_id)
            player = session.get(Giocatore, player_id)
            op_count = session.execute(text("SELECT COUNT(*) FROM operazioni")).scalar()
            statuses = {
                row[0]
                for row in session.execute(
                    text("SELECT status FROM semantic_undo_log")
                ).fetchall()
            }
        finally:
            session.close()

        self.assertEqual(result.inverse_action_type, "undo_acquisto_definitivo")
        self.assertEqual(seller.fm, 0)
        self.assertEqual(buyer.fm, 1000)
        self.assertEqual(player.squadra, "Seller")
        self.assertEqual(player.valore_svincolo, 100)
        self.assertEqual(op_count, 0)
        self.assertEqual(statuses, {"undone"})

    def test_svincolo_records_deleted_player_after_snapshot_as_null(self):
        team_id = self.seed_team("Team A", 100)
        player_id = self.seed_player("Released", "Team A", valore_svincolo=75)

        self.service.registra_svincolo(
            SvincoloCommand(
                giocatore_ids=[player_id],
                fq_id=team_id,
                data=datetime.date(2026, 8, 1),
            )
        )

        rows = self.semantic_rows()
        player_row = next(row for row in rows if row["entity_type"] == "giocatore")
        before = json.loads(player_row["before_snapshot"])
        self.assertEqual(before["nome"], "Released")
        self.assertIsNone(player_row["after_snapshot"])

    def test_undo_svincolo_recreates_deleted_player(self):
        team_id = self.seed_team("Team A", 100)
        player_id = self.seed_player("Released", "Team A", valore_svincolo=75)

        self.service.registra_svincolo(
            SvincoloCommand(
                giocatore_ids=[player_id],
                fq_id=team_id,
                data=datetime.date(2026, 8, 1),
            )
        )

        undo_transaction(self.Session, self.latest_transaction_id())

        session = self.Session()
        try:
            team = session.get(Fantasquadra, team_id)
            player = session.get(Giocatore, player_id)
            op_count = session.execute(text("SELECT COUNT(*) FROM operazioni")).scalar()
        finally:
            session.close()

        self.assertEqual(team.fm, 100)
        self.assertIsNotNone(player)
        self.assertEqual(player.nome, "Released")
        self.assertEqual(op_count, 0)

    def test_asta_manuale_records_created_player_before_snapshot_as_null(self):
        team_id = self.seed_team("Team A", 1000)

        self.service.registra_asta_manuale(
            AstaManualeCommand(
                fq_id=team_id,
                giocatori=[
                    AstaPlayerCommand(
                        nome="Created",
                        quotazione=10,
                        spesa=100,
                        estendi=False,
                    )
                ],
                data_asta=datetime.date(2026, 8, 1),
            )
        )

        rows = self.semantic_rows()
        player_row = next(row for row in rows if row["entity_type"] == "giocatore")
        after = json.loads(player_row["after_snapshot"])
        self.assertIsNone(player_row["before_snapshot"])
        self.assertEqual(after["nome"], "Created")

    def test_undo_asta_removes_created_player(self):
        team_id = self.seed_team("Team A", 1000)

        self.service.registra_asta_manuale(
            AstaManualeCommand(
                fq_id=team_id,
                giocatori=[
                    AstaPlayerCommand(
                        nome="Created",
                        quotazione=10,
                        spesa=100,
                        estendi=False,
                    )
                ],
                data_asta=datetime.date(2026, 8, 1),
            )
        )

        undo_transaction(self.Session, self.latest_transaction_id())

        session = self.Session()
        try:
            team = session.get(Fantasquadra, team_id)
            player_count = session.query(Giocatore).filter_by(nome="Created").count()
            op_count = session.execute(text("SELECT COUNT(*) FROM operazioni")).scalar()
        finally:
            session.close()

        self.assertEqual(team.fm, 1000)
        self.assertEqual(player_count, 0)
        self.assertEqual(op_count, 0)

    def test_undo_detects_conflict_when_entity_changed_after_operation(self):
        seller_id = self.seed_team("Seller", 0)
        buyer_id = self.seed_team("Buyer", 1000)
        player_id = self.seed_player("Sold Player", "Seller", valore_svincolo=100)

        self.service.registra_acquisto_definitivo(
            AcquistoDefinitivoCommand(
                giocatori=[PlayerQuoteCommand(id=player_id, quotazione=10)],
                fq_venditrice_id=seller_id,
                fq_acquirente_id=buyer_id,
                fm=200,
                data_acquisto=datetime.date(2026, 1, 1),
            )
        )
        transaction_id = self.latest_transaction_id()

        session = self.Session()
        try:
            player = session.get(Giocatore, player_id)
            player.convocato = True
            session.commit()
        finally:
            session.close()

        with self.assertRaises(SemanticUndoConflict):
            undo_transaction(self.Session, transaction_id)

    def test_prestito_records_semantic_audit(self):
        lender_id = self.seed_team("Lender", 100)
        receiver_id = self.seed_team("Receiver", 100)
        player_id = self.seed_player("Loaned", "Lender", valore_svincolo=50)

        self.service.registra_prestito(
            PrestitoCommand(
                giocatori=[
                    PlayerLoanCommand(
                        id=player_id,
                        fine_prestito=datetime.date(2027, 7, 1),
                    )
                ],
                fq_prestante_id=lender_id,
                fq_ricevente_id=receiver_id,
                fm=10,
                inizio_prestito=datetime.date(2026, 8, 1),
            )
        )

        self.assertIn("prestito", self.operation_types_in_audit())

    def test_scambio_prestiti_records_semantic_audit(self):
        team_a_id = self.seed_team("Team A", 100)
        team_b_id = self.seed_team("Team B", 100)
        player_a_id = self.seed_player("Loan A", "Team A", valore_svincolo=50)
        player_b_id = self.seed_player("Loan B", "Team B", valore_svincolo=60)

        self.service.registra_scambio_prestiti(
            ScambioPrestitiCommand(
                giocatori_a=[
                    PlayerLoanCommand(
                        id=player_a_id,
                        fine_prestito=datetime.date(2027, 7, 1),
                    )
                ],
                giocatori_b=[
                    PlayerLoanCommand(
                        id=player_b_id,
                        fine_prestito=datetime.date(2027, 7, 1),
                    )
                ],
                fq_a_id=team_a_id,
                fq_b_id=team_b_id,
                fm=0,
                inizio_prestito=datetime.date(2026, 8, 1),
            )
        )

        self.assertIn("scambio prestiti", self.operation_types_in_audit())

    def test_scambio_definitivo_records_semantic_audit(self):
        team_a_id = self.seed_team("Team A", 100)
        team_b_id = self.seed_team("Team B", 100)
        player_a_id = self.seed_player("Swap A", "Team A", valore_svincolo=50)
        player_b_id = self.seed_player("Swap B", "Team B", valore_svincolo=60)

        self.service.registra_scambio_definitivo(
            ScambioDefinitivoCommand(
                giocatori_a=[PlayerQuoteCommand(id=player_a_id, quotazione=10)],
                giocatori_b=[PlayerQuoteCommand(id=player_b_id, quotazione=10)],
                fq_a_id=team_a_id,
                fq_b_id=team_b_id,
                fm=0,
                data_acquisto=datetime.date(2026, 8, 1),
            )
        )

        self.assertIn("scambio definitivo", self.operation_types_in_audit())

    def test_aumento_contratto_records_semantic_audit(self):
        team_id = self.seed_team("Team A", 1000)
        player_id = self.seed_player("Extended", "Team A", valore_svincolo=100)

        self.service.registra_aumento_contratto(
            AumentoContrattoCommand(
                fq_id=team_id,
                giocatore_ids=[player_id],
            )
        )

        self.assertIn("aumento contratto", self.operation_types_in_audit())

    def test_importa_asta_records_semantic_audit(self):
        self.seed_team("Team A", 1000)

        self.service.importa_asta(
            ImportaAstaCommand(
                asta_data=[
                    {
                        "nome": "Imported",
                        "fq_nome": "Team A",
                        "spesa": 100,
                        "quotazione": 10,
                    }
                ],
                data_asta=datetime.date(2026, 8, 1),
            )
        )

        self.assertIn("asta", self.operation_types_in_audit())


if __name__ == "__main__":
    unittest.main()
