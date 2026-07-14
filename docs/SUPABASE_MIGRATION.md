# Supabase migration plan

## Obiettivo

Portare su Supabase/Postgres la prima baseline dei dati oggi contenuti in
`fantamanager.db`, mantenendo SQLite nel progetto come storage locale per undo,
recovery rapida, cache e possibili flussi offline/retry.

La prima fase ha preparato schema e dati remoti in modo verificabile. La fase
successiva introduce la persistenza ibrida: l'app continua a scrivere prima su
SQLite per mantenere undo/recovery locali, poi puo' sincronizzare lo snapshot
verso Supabase in modalita manuale o automatica.

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
- `persistence/`
  - gateway runtime per push/pull snapshot SQLite/Supabase;
  - stato locale del sync in `sync_state`;
  - listener opzionale post-commit per sync automatico.
- `scripts/sync_supabase.py`
  - comando manuale per `push`, `pull` e `status`.

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
- Auth runtime desktop: per ora la connessione remota usa una URL Postgres via
  variabile d'ambiente. Prima di distribuire l'app andra' evitato di esporre
  credenziali dirette nel client.

## Persistenza ibrida runtime

La persistenza ibrida lavora come snapshot mirror:

- SQLite resta il database locale usato dall'app, dall'undo e dalle recovery
  rapide.
- Supabase/Postgres riceve uno snapshot coerente delle quattro tabelle
  applicative.
- Se Supabase non e' configurato o non raggiungibile, i commit locali non
  vengono bloccati; lo stato dell'ultimo sync resta in `sync_state`.
- Le righe non valide di `operazione_giocatori` vengono saltate anche nel sync
  runtime, come nel seed export.

### Configurazione `.env`

Prerequisito per il sync runtime:

```powershell
python -m pip install "psycopg[binary]"
```

La configurazione runtime viene letta automaticamente dal file locale `.env`.
Il file `.env` e' ignorato da Git, mentre `.env.example` resta come template
committabile.

Configurare la URL Postgres/Supabase in `.env`:

```dotenv
FANTAMANAGER_SUPABASE_DB_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/postgres?sslmode=require
```

In alternativa sono lette anche:

- `FANTAMANAGER_REMOTE_DATABASE_URL`
- `SUPABASE_DB_URL`

Modalita sync:

```dotenv
FANTAMANAGER_SYNC_MODE=manual
```

Valori:

- `off`: sync disabilitato.
- `manual`: sync solo da menu o script.
- `auto`: dopo ogni commit ORM locale viene eseguito un push snapshot verso
  Supabase.

Pull automatico all'avvio, da usare solo quando il remoto e' sicuramente la
fonte corretta:

```dotenv
FANTAMANAGER_SYNC_PULL_ON_START=true
```

Nel file `.env` sono presenti anche le chiavi API Supabase:

```dotenv
FANTAMANAGER_SUPABASE_URL=
FANTAMANAGER_SUPABASE_ANON_KEY=
FANTAMANAGER_SUPABASE_SERVICE_ROLE_KEY=
```

Queste chiavi sono predisposte per il futuro passaggio a sync via API/RLS. Il
sync attuale usa invece la connection string Postgres
`FANTAMANAGER_SUPABASE_DB_URL`, perche' SQLAlchemy comunica direttamente con il
database Postgres del progetto Supabase.

### Comandi manuali

Stato locale:

```powershell
python scripts/sync_supabase.py status
```

Push SQLite locale verso Supabase:

```powershell
python scripts/sync_supabase.py push
```

Pull Supabase verso SQLite locale:

```powershell
python scripts/sync_supabase.py pull --yes
```

Il pull sostituisce i dati SQLite locali con lo snapshot remoto; prima di usarlo
conviene avere uno snapshot/backup locale recente.
