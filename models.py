from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
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


class Stagione(Base):
    __tablename__ = "stagioni"

    id = Column(Integer, primary_key=True)
    codice = Column(String, nullable=False, unique=True)
    anno_inizio = Column(Integer, nullable=False)
    anno_fine = Column(Integer, nullable=False)
    data_inizio = Column(Date, nullable=False)
    data_fine = Column(Date, nullable=True)
    stato = Column(String, nullable=False, default="attiva")
    fase_corrente = Column(String, nullable=True)
    storage_path = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    deleted = Column(Boolean, default=False)

    fasi = relationship(
        "StagioneFase",
        back_populates="stagione",
        cascade="all, delete-orphan",
    )
    files = relationship(
        "StagioneFile",
        back_populates="stagione",
        cascade="all, delete-orphan",
    )
    step_logs = relationship(
        "StagioneStepLog",
        back_populates="stagione",
        cascade="all, delete-orphan",
    )


class StagioneFase(Base):
    __tablename__ = "stagione_fasi"
    __table_args__ = (
        UniqueConstraint("stagione_id", "codice_fase", name="uq_stagione_fase"),
    )

    id = Column(Integer, primary_key=True)
    stagione_id = Column(Integer, ForeignKey("stagioni.id"), nullable=False)
    codice_fase = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    data_inizio = Column(Date, nullable=True)
    data_fine = Column(Date, nullable=True)
    stato = Column(String, nullable=False, default="pianificata")
    asta_data_inizio = Column(Date, nullable=True)
    asta_data_fine = Column(Date, nullable=True)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    stagione = relationship("Stagione", back_populates="fasi")
    files = relationship("StagioneFile", back_populates="fase")
    step_logs = relationship("StagioneStepLog", back_populates="fase")


class StagioneFile(Base):
    __tablename__ = "stagione_files"

    id = Column(Integer, primary_key=True)
    stagione_id = Column(Integer, ForeignKey("stagioni.id"), nullable=False)
    fase_id = Column(Integer, ForeignKey("stagione_fasi.id"), nullable=True)
    tipo_file = Column(String, nullable=False)
    nome_logico = Column(String, nullable=False)
    path = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)

    stagione = relationship("Stagione", back_populates="files")
    fase = relationship("StagioneFase", back_populates="files")


class StagioneStepLog(Base):
    __tablename__ = "stagione_step_log"

    id = Column(Integer, primary_key=True)
    stagione_id = Column(Integer, ForeignKey("stagioni.id"), nullable=False)
    fase_id = Column(Integer, ForeignKey("stagione_fasi.id"), nullable=True)
    step_key = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)

    stagione = relationship("Stagione", back_populates="step_logs")
    fase = relationship("StagioneFase", back_populates="step_logs")


TIPI_OPERAZIONE = [
    "acquisto definitivo",
    "scambio definitivo",
    "prestito",
    "scambio prestiti",
    "svincolo",
    "svincolo fine contratto",
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
    stagione_id = Column(Integer, ForeignKey("stagioni.id"), nullable=True)
    fase_stagione = Column(String, nullable=True)
    periodo_regolamento = Column(String, nullable=True)
    mese_regolamento = Column(String, nullable=True)
    # Stable JSON payload used by history cards/reports without depending on
    # the current state of players or teams.
    operation_snapshot = Column(Text, nullable=True)

    # Relationships
    fantasquadra_a = relationship("Fantasquadra", foreign_keys=[fantasquadra_a_id])
    fantasquadra_b = relationship("Fantasquadra", foreign_keys=[fantasquadra_b_id])
    conguaglio_da = relationship("Fantasquadra", foreign_keys=[conguaglio_da_id])
    stagione = relationship("Stagione", foreign_keys=[stagione_id])

    giocatori = relationship(
        "Giocatore",
        secondary=operazione_giocatori,
        back_populates="operazioni",
    )
