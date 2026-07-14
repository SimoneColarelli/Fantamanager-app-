import datetime
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Fantasquadra, Giocatore, Operazione
from persistence.snapshot_sync import SnapshotSyncGateway


class HybridPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.local_engine = create_engine("sqlite:///:memory:")
        self.remote_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.local_engine)
        Base.metadata.create_all(self.remote_engine)
        self.Session = sessionmaker(
            bind=self.local_engine,
            autocommit=False,
            autoflush=False,
        )

    def tearDown(self):
        Base.metadata.drop_all(self.local_engine)
        Base.metadata.drop_all(self.remote_engine)
        self.local_engine.dispose()
        self.remote_engine.dispose()

    def test_push_local_to_remote_skips_invalid_operation_links(self):
        session = self.Session()
        try:
            team = Fantasquadra(id=1, nome="Team A", fm=100, deleted=False)
            player = Giocatore(
                id=10,
                nome="Player A",
                squadra="Team A",
                spesa=1,
                data_acquisto=datetime.date(2026, 1, 1),
                fascia="1",
                quotazione=10,
                dq=0,
                valore_svincolo=1,
                scadenza_contratto=datetime.date(2028, 7, 1),
                convocato=True,
                in_serie_a=True,
                deleted=False,
            )
            operation = Operazione(
                id=20,
                fantasquadra_a_id=1,
                tipo_operazione="asta",
                conguaglio=0,
                data=datetime.date(2026, 7, 1),
                clausole="",
            )
            operation.giocatori = [player]
            session.add_all([team, player, operation])
            session.commit()
            session.execute(
                text(
                    """
                    INSERT INTO operazione_giocatori (operazione_id, giocatore_id)
                    VALUES (99, 10)
                    """
                )
            )
            session.commit()
        finally:
            session.close()

        gateway = SnapshotSyncGateway(self.Session, self.remote_engine)
        result = gateway.push_local_to_remote()

        with self.remote_engine.connect() as connection:
            teams = connection.execute(text("SELECT COUNT(*) FROM fantasquadre")).scalar()
            players = connection.execute(text("SELECT COUNT(*) FROM giocatori")).scalar()
            operations = connection.execute(text("SELECT COUNT(*) FROM operazioni")).scalar()
            links = connection.execute(
                text("SELECT COUNT(*) FROM operazione_giocatori")
            ).scalar()

        self.assertTrue(result.ok)
        self.assertEqual(teams, 1)
        self.assertEqual(players, 1)
        self.assertEqual(operations, 1)
        self.assertEqual(links, 1)
        self.assertEqual(
            result.skipped_links,
            [
                {
                    "operazione_id": 99,
                    "giocatore_id": 10,
                    "reason": "missing operazione",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
