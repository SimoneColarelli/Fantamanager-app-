from sqlalchemy import Column, Integer, String, Boolean
from database import Base


class Giocatore(Base):
    __tablename__ = "giocatori"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    squadra = Column(String)
    ruolo = Column(String)
    prezzo = Column(Integer)
    deleted = Column(Boolean, default=False)


class Fantasquadra(Base):
    __tablename__ = "fantasquadre"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    allenatore = Column(String)
    crediti = Column(Integer)
    deleted = Column(Boolean, default=False)