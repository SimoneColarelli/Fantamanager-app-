import pandas as pd

def load_excel(path: str) -> dict:
    """
    Ritorna:
    {
        "Nome Giocatore": quotazione
    }
    """
    df = pd.read_excel(path, engine="openpyxl")
    df = df.iloc[1:]  # dalla seconda riga

    excel_data = {}
    for _, row in df.iterrows():
        nome = str(row[3]).strip()
        quotazione = int(row[8])
        excel_data[nome] = quotazione

    return excel_data
