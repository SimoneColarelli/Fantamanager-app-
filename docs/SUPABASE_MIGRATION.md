# Supabase migration plan

## Obiettivo

Portare su Supabase/Postgres la prima baseline dei dati oggi contenuti in
`fantamanager.db`, mantenendo SQLite nel progetto come storage locale per undo,
recovery rapida, cache e possibili flussi offline/retry.

Questa fase non cambia ancora il runtime dell'app desktop: prepara schema e dati
remoti in modo verificabile. Il passaggio successivo sara' introdurre un gateway
di persistenza Supabase dietro al layer service/repository.

## Stato rilevato

- Il progetto non aveva ancora una cartella `supabase/`.
- La Supabase CLI non risulta installata localmente.
- Lo schema SQLite attuale contiene:
  - `fantasquadre`
  - `giocatori`
  - `operazioni`
  - `operazione_giocatori`
- Il DB locale contiene 8 fantasquadre, 280 giocatori, 12 operazioni e 80 righe
  nella tabella ponte.
- Sono presenti 2 righe orfane in `operazione_giocatori` verso una operazione
  non piu' esistente. Il seed le esclude, perche' Postgres applica FK reali.

## File introdotti

- `supabase/migrations/20260714000100_initial_schema.sql`
  - baseline Postgres equivalente al modello SQLite attuale;
  - vincoli FK su operazioni, squadre e giocatori;
  - indici sulle colonne piu' usate per filtri e join.
- `scripts/export_sqlite_to_supabase_seed.py`
  - genera `supabase/seed.sql` da `fantamanager.db`;
  - conserva gli ID originali;
  - scarta le sole righe ponte non valide;
  - riallinea le identity sequence Postgres.
- `supabase/seed.sql`
  - seed generato dai dati SQLite versionati.

## Procedura operativa

1. Rigenerare il seed quando cambiano i dati SQLite versionati:

   ```powershell
   python scripts/export_sqlite_to_supabase_seed.py --db fantamanager.db --out supabase/seed.sql
   ```

2. Applicare la migration al progetto Supabase.

   Se la GitHub integration del progetto Supabase legge le migration dal repo,
   fare push della cartella `supabase/`. In alternativa aprire il file
   `supabase/migrations/20260714000100_initial_schema.sql` nel SQL editor di
   Supabase ed eseguirlo una volta.

3. Caricare i dati iniziali.

   Eseguire `supabase/seed.sql` nel SQL editor di Supabase. Il seed di default
   e' distruttivo per queste quattro tabelle:

   - `operazione_giocatori`
   - `operazioni`
   - `giocatori`
   - `fantasquadre`

   Per generare un seed non distruttivo usare:

   ```powershell
   python scripts/export_sqlite_to_supabase_seed.py --no-truncate
   ```

4. Verificare i conteggi su Supabase:

   ```sql
   select count(*) from public.fantasquadre;
   select count(*) from public.giocatori;
   select count(*) from public.operazioni;
   select count(*) from public.operazione_giocatori;
   ```

   Valori attesi dopo il seed corrente:

   - `fantasquadre`: 8
   - `giocatori`: 280
   - `operazioni`: 12
   - `operazione_giocatori`: 78

## Decisioni rimandate

- Auth e Row Level Security: non abilitate nella baseline per non bloccare la
  prima importazione dati.
- Normalizzazione di `giocatori.squadra` e `giocatori.in_prestito_a`: restano
  campi testo per fedelta' con SQLite; una migration successiva potra'
  introdurre FK verso `fantasquadre`.
- Sync runtime: l'app continuera' a scrivere su SQLite finche' non sara'
  introdotto un gateway Supabase nel layer service/repository.
- Undo remoto: SQLite resta responsabile degli snapshot locali; la semantica
  degli undo gia' sincronizzati andra' decisa prima delle scritture remote.
