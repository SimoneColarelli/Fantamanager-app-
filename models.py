from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, Table, Text
from sqlalchemy.orm import relationship
from database import Base


# Association table: many-to-many between Operazione and Giocatore
operazione_giocatori = Table(
    "operazione_giocatori",
    Base.metadata,
    Column("operazione_id", Integer, ForeignKey("operazioni.id"), primary_key=True),
    Column("giocatore_id", Integer, ForeignKey("giocatori.id"), primary_key=True),
)


class Giocatore(Base):
    __tablename__ = "giocatori"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    squadra = Column(String)
    fantasquadra_id = Column(Integer, ForeignKey("fantasquadre.id"), nullable=True)
    spesa = Column(Integer)
    data_acquisto = Column(Date)
    fascia = Column(String)
    quotazione = Column(Integer)
    dq = Column(Integer)
    valore_svincolo = Column(Integer)
    scadenza_contratto = Column(Date)
    in_prestito_a = Column(String, nullable=True)
    prestito_a_fantasquadra_id = Column(Integer, ForeignKey("fantasquadre.id"), nullable=True)
    inizio_prestito = Column(Date, nullable=True)
    fine_prestito = Column(Date, nullable=True)
    convocato = Column(Boolean, default=True)
    in_serie_a = Column(Boolean, default=True)
    deleted = Column(Boolean, default=False)

    # Back-reference to operations this player is involved in
    operazioni = relationship(
        "Operazione",
        secondary=operazione_giocatori,
        back_populates="giocatori",
    )
    fantasquadra = relationship("Fantasquadra", foreign_keys=[fantasquadra_id])
    prestito_a_fantasquadra = relationship(
        "Fantasquadra",
        foreign_keys=[prestito_a_fantasquadra_id],
    )


class Fantasquadra(Base):
    __tablename__ = "fantasquadre"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    fm = Column(Integer, nullable=False)
    campionati = Column(Integer, default=0)
    coppe = Column(Integer, default=0)
    supercoppe = Column(Integer, default=0)
    deleted = Column(Boolean, default=False)


TIPI_OPERAZIONE = [
    "acquisto definitivo",
    "scambio definitivo",
    "prestito",
    "scambio prestiti",
    "svincolo",
    "asta",
    "aumento contratto",
]


class Operazione(Base):
    __tablename__ = "operazioni"

    id = Column(Integer, primary_key=True)

    # The two clubs involved (fantasquadra_b_id may be NULL for "svincolo")
    fantasquadra_a_id = Column(Integer, ForeignKey("fantasquadre.id"), nullable=False)
    fantasquadra_b_id = Column(Integer, ForeignKey("fantasquadre.id"), nullable=True)

    tipo_operazione = Column(String, nullable=False)

    # Cash adjustment and which club pays it
    conguaglio = Column(Integer, default=0)
    conguaglio_da_id = Column(Integer, ForeignKey("fantasquadre.id"), nullable=True)

    data = Column(Date, nullable=True)
    clausole = Column(String, nullable=True)
    # Stable JSON payload used by history cards/reports without depending on
    # the current state of players or teams.
    operation_snapshot = Column(Text, nullable=True)

    # Relationships
    fantasquadra_a = relationship("Fantasquadra", foreign_keys=[fantasquadra_a_id])
    fantasquadra_b = relationship("Fantasquadra", foreign_keys=[fantasquadra_b_id])
    conguaglio_da = relationship("Fantasquadra", foreign_keys=[conguaglio_da_id])

    giocatori = relationship(
        "Giocatore",
        secondary=operazione_giocatori,
        back_populates="operazioni",
    )
