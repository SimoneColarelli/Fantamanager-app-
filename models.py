from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base, SessionLocal

class Fantasquadra(Base):
    __tablename__ = "fantasquadre"

    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)
    fm = Column(Integer, default=0)
    campionati = Column(Integer, default=0)
    coppe = Column(Integer, default=0)
    supercoppe = Column(Integer, default=0)

class Giocatore(Base):
    __tablename__ = "giocatori"

    id = Column(Integer, primary_key=True)
    nome = Column(String, unique=True, nullable=False)

    squadra_id = Column(Integer, ForeignKey("fantasquadre.id"))
    in_prestito_a = Column(Integer, ForeignKey("fantasquadre.id"), nullable=True)

    spesa = Column(Integer, default=1)
    data_acquisto = Column(String)
    fascia = Column(Integer)
    quotazione = Column(Integer)
    dq = Column(Integer, default=0)
    valore_svincolo = Column(Integer)

    scadenza_contratto = Column(String)
    inizio_prestito = Column(String)
    fine_prestito = Column(String)

    convocato = Column(Boolean, default=False)
    in_serie_a = Column(Boolean, default=True)

    def get_squadra(self):
        session = SessionLocal()
        return (session.query(Fantasquadra).filter(Fantasquadra.id == self.squadra_id).one_or_none()).nome
