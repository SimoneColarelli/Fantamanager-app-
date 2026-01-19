from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

ENGINE = create_engine("sqlite:///fantacalcio.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=ENGINE, future=True)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(ENGINE)
