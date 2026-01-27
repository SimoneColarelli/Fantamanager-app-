def prettify(name: str) -> str:
    return name.replace("_", " ").capitalize()

GIOCATORI_FIELDS = ["nome", "squadra", "spesa", "data_acquisto", "fascia", "quotazione", "dq", "valore_svincolo", "scadenza_contratto", "in_prestito_a", "inizio_prestito", "fine_prestito", "convocato", "in_serie_a"]
GIOCATORI_HEADERS = [prettify(field) for field in GIOCATORI_FIELDS]

FANTASQUADRE_FIELDS = ["nome", "fm", "campionati", "coppe", "supercoppe"]
FANTASQUADRE_HEADERS = [prettify(field) for field in FANTASQUADRE_FIELDS]