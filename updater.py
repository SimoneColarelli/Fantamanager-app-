from models import Giocatore

def f(v, d):
    table = [
        (1, 50, 21.5, -3),
        (50, 100, 18, -8),
        (100, 200, 12, -12),
        (200, 400, 8, -18),
        (400, 600, 3, -21.5),
        (600, float("inf"), 1, -30),
    ]
    for low, high, pos, neg in table:
        if low <= v < high:
            return pos if d > 0 else neg

def update_completo(session, excel_data: dict):
    try:
        with session.begin():
            for g in session.query(Giocatore).all():

                if g.nome not in excel_data:
                    g.in_serie_a = False
                    continue

                g.in_serie_a = True
                x = excel_data[g.nome]

                if g.in_prestito_a is not None:
                    g.quotazione = x
                    continue

                d = x - g.quotazione
                s = g.spesa

                while d != 0:
                    s += f(s, d)
                    d = d - 1 if d > 0 else d + 1

                g.valore_svincolo = int(s)
                g.dq += (x - g.quotazione)
                g.quotazione = x

    except Exception as e:
        raise RuntimeError(f"Update completo fallito: {e}")

def update_solo_quotazioni(session, excel_data: dict):
    try:
        with session.begin():
            for g in session.query(Giocatore).all():
                if g.nome not in excel_data:
                    g.in_serie_a = False
                else:
                    g.in_serie_a = True
                    g.quotazione = excel_data[g.nome]
    except Exception as e:
        raise RuntimeError(f"Update quotazioni fallito: {e}")
