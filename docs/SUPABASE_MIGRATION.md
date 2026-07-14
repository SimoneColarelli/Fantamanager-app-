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
- `supabase/migrations/20260714000300_normalize_giocatore_team_refs.sql`
  - aggiunge FK normalizzate da `giocatori` a `fantasquadre`;
  - mantiene i campi testo `squadra` e `in_prestito_a` per compatibilita';
  - popola le nuove FK dai dati storici gia' presenti.
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

2. Applicare le migration al progetto Supabase.

   Se la GitHub integration del progetto Supabase legge le migration dal repo,
   fare push della cartella `supabase/`. In alternativa aprire i file in
   `supabase/migrations/` nel SQL editor di Supabase ed eseguirli in ordine.

   Prima di usare un nuovo push/sync dall'app, il progetto Supabase deve avere
   anche la migration `20260714000300_normalize_giocatore_team_refs.sql`,
   perche' lo snapshot runtime ora include `fantasquadra_id` e
   `prestito_a_fantasquadra_id`.

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
- Auth runtime desktop: per ora la connessione remota usa una URL Postgres via
  variabile d'ambiente. Prima di distribuire l'app andra' evitato di esporre
  credenziali dirette nel client.

## Normalizzazione riferimenti fantasquadra

La normalizzazione e' stata introdotta in modo compatibile:

- `giocatori.squadra` resta il campo testo storico usato dalla UI.
- `giocatori.fantasquadra_id` contiene la FK verso la fantasquadra proprietaria.
- `giocatori.in_prestito_a` resta il campo testo storico per il prestito.
- `giocatori.prestito_a_fantasquadra_id` contiene la FK verso la fantasquadra
  che riceve il giocatore in prestito.

Le operazioni di mercato e le modifiche manuali dalla tabella mantengono
allineati campo testo e FK. Le FK sono nullable per permettere import storici,
nomi non riconosciuti e migrazioni progressive senza bloccare l'app.

## Persistenza ibrida runtime

La persistenza ibrida lavora come snapshot mirror:

- SQLite resta il database locale usato dall'app, dall'undo e dalle recovery
  rapide.
- Il client desktop e' uno solo: non e' previsto un workflow multi-client con
  merge concorrenti.
- Supabase/Postgres riceve uno snapshot coerente delle quattro tabelle
  applicative finche' non sara' attivo il sync per evento.
- Se Supabase non e' configurato o non raggiungibile, i commit locali non
  vengono bloccati; lo stato dell'ultimo sync resta in `sync_state`.
- Le righe non valide di `operazione_giocatori` vengono saltate anche nel sync
  runtime, come nel seed export.

### Backup, undo semantico e retry

I backup e gli undo non sono lo stesso meccanismo:

- Backup: JSON snapshot completo o per tabella, esposto nella UI come
  `Data > Backup`.
- Undo snapshot: ripristino rapido locale dell'intero SQLite tramite
  `UndoManager`, utile come recovery immediata.
- Undo semantico: feature da completare usando `semantic_undo_log`, con audit
  before/after per annullare una singola transazione o operazione senza
  ripristinare tutto il dataset.

La base DB locale per il prossimo step e' gia' prevista:

- `sync_outbox`: coda persistente di eventi da sincronizzare.
- `entity_versions`: versioning locale/remoto per rilevare desincronizzazioni.
- `semantic_undo_log`: audit log per rollback semantici mirati.

Stato corrente del semantic undo:

- Tutte le operazioni di mercato scrivono righe audit in `semantic_undo_log`.
- Ogni riga audit conserva snapshot `before` e `after` dell'entita' toccata.
- Ogni tipo di operazione ha una `inverse_action_type` esplicita:
  - `undo_acquisto_definitivo`
  - `undo_scambio_definitivo`
  - `undo_prestito`
  - `undo_scambio_prestiti`
  - `undo_svincolo`
  - `undo_asta`
  - `undo_aumento_contratto`
- L'esecuzione dell'undo semantico e' implementata:
  - CLI: `python scripts/semantic_undo.py list`
  - CLI: `python scripts/semantic_undo.py undo --latest`
  - UI: `Modifica > Annulla operazione auditata...`
- L'undo semantico usa controlli strict: se una entita' toccata e' cambiata
  dopo la transazione, l'annullamento viene bloccato per evitare ripristini
  ambigui.

I prossimi passaggi saranno:

1. Aggiungere nello storico operazioni una card/marker visibile per operazioni
   annullate semanticamente.
2. Accodare eventi applicativi reali in `sync_outbox`.
3. In caso di errore sync aggiornare `retry_count`, `last_error` e
   `next_attempt_at`.
4. A sync riuscito marcare gli eventi come `synced` e aggiornare le versioni.

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
