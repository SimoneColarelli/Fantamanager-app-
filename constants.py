def prettify(name: str) -> str:
    if name == "squadra_id":
        return "Squadra"
    return name.replace("_", " ").capitalize()


GIOCATORI_FIELDS = [
    "nome",
    "squadra_id",
    "spesa",
    "data_acquisto",
    "fascia",
    "quotazione",
    "dq",
    "valore_svincolo",
    "scadenza_contratto",
    "in_prestito_a",
    "inizio_prestito",
    "fine_prestito",
    "convocato",
    "in_serie_a",
]

FANTASQUADRE_FIELDS = [
    "nome",
    "fm",
    "campionati",
    "coppe",
    "supercoppe",
]

GIOCATORI_HEADERS = [prettify(f) for f in GIOCATORI_FIELDS]
FANTASQUADRE_HEADERS = [prettify(f) for f in FANTASQUADRE_FIELDS]
