import sqlite3

conn = sqlite3.connect('fantamanager.db')
cursor = conn.cursor()

query = """
UPDATE operazioni 
SET tipo_operazione = 'asta' 
WHERE tipo_operazione = 'acquisto definitivo' 
AND clausole = 'Importato da asta'
"""

cursor.execute(query)
conn.commit()

print(f"{cursor.rowcount} righe aggiornate con successo.")
conn.close()