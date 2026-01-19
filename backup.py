import json
from sqlalchemy import text
from models import Fantasquadra, Giocatore


def export_db(session, path: str):
    """
    Export database to JSON (used for manual export).
    """
    data = {
        "fantasquadre": [],
        "giocatori": []
    }

    for f in session.query(Fantasquadra).all():
        d = f.__dict__.copy()
        d.pop("_sa_instance_state", None)
        data["fantasquadre"].append(d)

    for g in session.query(Giocatore).all():
        d = g.__dict__.copy()
        d.pop("_sa_instance_state", None)
        data["giocatori"].append(d)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def import_db(session, path: str):
    """
    Import database from JSON safely.
    Used by Undo and Import DB.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Clear tables with proper transaction handling
    session.query(Giocatore).delete()
    session.query(Fantasquadra).delete()
    session.commit()

    # Restore Fantasquadre
    for f in data.get("fantasquadre", []):
        session.add(Fantasquadra(**f))
    session.commit()

    # Restore Giocatori
    for g in data.get("giocatori", []):
        session.add(Giocatore(**g))
    session.commit()