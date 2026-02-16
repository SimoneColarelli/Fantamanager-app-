from sqlalchemy import Column, Integer, String, Boolean, Date, Float
from database import Base


class Giocatore(Base):
    __tablename__ = "giocatori"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    squadra = Column(String)
    spesa = Column(Float)
    data_acquisto = Column(Date)
    fascia = Column(String)
    quotazione = Column(Integer)
    dq = Column(Integer)
    valore_svincolo = Column(Float)
    scadenza_contratto = Column(Date)
    in_prestito_a = Column(Integer, nullable=True)  # Foreign key to Fantasquadra.id, can be null
    inizio_prestito = Column(Date, nullable=True)
    fine_prestito = Column(Date, nullable=True )
    convocato = Column(Boolean, default=True)
    in_serie_a = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)


class Fantasquadra(Base):
    __tablename__ = "fantasquadre"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    fm = Column(String)
    campionati = Column(Integer, default=0)
    coppe = Column(Integer, default=0)
    supercoppe = Column(Integer, default=0)
    deleted = Column(Boolean, default=False)