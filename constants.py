def prettify(name: str) -> str:
    return name.replace("_", " ").capitalize()

GIOCATORI_FIELDS = ["nome", "squadra", "spesa", "data_acquisto", "fascia", "quotazione", "dq", "valore_svincolo", "scadenza_contratto", "in_prestito_a", "inizio_prestito", "fine_prestito", "convocato", "in_serie_a"]
GIOCATORI_HEADERS = [prettify(field) for field in GIOCATORI_FIELDS]

FANTASQUADRE_FIELDS = ["nome", "fm", "campionati", "coppe", "supercoppe"]
FANTASQUADRE_HEADERS = [prettify(field) for field in FANTASQUADRE_FIELDS]

def calculate_fascia(spesa: int) -> int:
    if spesa >= 0 and spesa <= 49:
        return 1
    elif spesa >= 50 and spesa <= 99:
        return 2
    elif spesa >= 100 and spesa <= 199:
        return 3
    elif spesa >= 200 and spesa <= 399:
        return 4
    elif spesa >= 400 and spesa <= 599:
        return 5
    elif spesa >= 600:
        return 6
    else:
        return 0  # Invalid fascia, can be handled as needed
    
FANTASQUADRE_NAMES = ["Zarro Team", 
                      "I Cammelloni",
                      "Bomberonoi",
                      "Atletico Abusivo",
                      "Real Madrink",
                      "Spal Letti",
                      "Bayern Muten",
                      "Red Dragon"]