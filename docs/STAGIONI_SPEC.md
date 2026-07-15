# Feature Stagioni

## 1. Obiettivo

Introdurre nel sistema una gestione strutturata delle stagioni, con una stagione
attiva che diventa stato applicativo corrente e guida:

- date e contesto delle operazioni di mercato;
- caricamento dei file quotazioni;
- update giocatori e presenza in Serie A;
- backup stagionali;
- gestione aste estiva/invernale;
- chiusura sessioni di mercato;
- svincoli di fine contratto a fine stagione.

La feature deve essere integrata con l'architettura esistente:

- UI desktop PySide6;
- database SQLite locale;
- migrazioni schema;
- persistenza ibrida SQLite + Supabase;
- service layer;
- UnitOfWork;
- semantic undo/audit;
- backup JSON gia' presenti tramite `DataManagerUI`;
- tab `Mercato` e logica import asta esistente.

## 2. Definizioni di dominio

### 2.1 Stagione

Una stagione e' identificata da un codice testuale nel formato:

```text
20xy/20x(y+1)
```

Esempi:

- `2026/2027`
- `2027/2028`

Ogni stagione ha:

- anno di inizio;
- anno di fine;
- data di inizio stagione;
- data eventuale di chiusura stagione;
- stato: `bozza`, `attiva`, `chiusa`;
- fase corrente calcolata o impostata;
- percorso storage locale dedicato.

### 2.2 Fasi

Una stagione e' composta da 3 fasi operative.

#### Fase 1: inizio stagione e sessione mercato estiva

Coincide con l'inizio della stagione e con la sessione di mercato estiva.
Coinvolge normalmente parte di agosto e settembre.

In questa fase avvengono:

- caricamento quotazioni iniziali stagione;
- update quotazioni;
- update presenza in Serie A;
- backup giocatori/fantasquadre di inizio stagione;
- operazioni di mercato estive;
- asta estiva;
- backup pre/post asta estiva;
- chiusura sessione estiva;
- backup di chiusura sessione estiva.

Le date di inizio/fine fase e le date dell'asta estiva devono essere
configurabili stagione per stagione.

#### Fase 2: sessione mercato invernale

Coincide con la sessione di mercato invernale.
Parte normalmente a gennaio e termina normalmente a febbraio.

In questa fase avvengono:

- caricamento quotazioni inizio sessione invernale;
- complete update;
- backup giocatori/fantasquadre di inizio sessione invernale;
- operazioni di mercato invernali;
- asta di riparazione invernale;
- backup pre/post asta invernale;
- chiusura sessione invernale;
- backup di chiusura sessione invernale.

Le date di inizio/fine fase e le date dell'asta invernale devono essere
configurabili stagione per stagione.

#### Fase 3: fine stagione

Coincide con la fine della stagione, normalmente a maggio/giugno in
corrispondenza della fine del campionato di Serie A.

Nota di dominio:

- il mese successivo a giugno non deve piu' essere usato come mese di fine
  stagione;
- tutti i riferimenti alla vecchia convenzione devono essere sostituiti con
  giugno.

In questa fase avvengono:

- caricamento quotazioni fine stagione;
- complete update;
- backup giocatori/fantasquadre fine stagione;
- svincolo dei giocatori con contratto in scadenza a giugno dell'anno di fine
  stagione;
- registrazione/audit degli svincoli di fine contratto;
- backup operazioni di fine stagione.

### 2.3 Stato intermedio

Tra una fase e l'altra lo stato della stagione e':

```text
campionato in corso
```

In questo stato la stagione resta attiva, ma non e' aperta una sessione di
mercato.

## 3. Stato corrente applicativo

La stagione attiva deve diventare uno stato corrente dell'applicazione.

Questo stato deve influenzare:

- default dei campi data/periodo nelle operazioni di mercato;
- sezioni abilitate nel tab `Stagioni`;
- percorsi di salvataggio dei file;
- naming automatico dei backup;
- fase associata alle operazioni create;
- filtri futuri per storico, dashboard e report.

## 4. UI richiesta

### 4.1 Nuovo tab

Aggiungere un tab principale:

```text
Stagioni
```

Il tab deve mostrare come primo elemento la dashboard della stagione attiva, se
presente.

Se non esiste una stagione attiva, deve mostrare una call-to-action per crearne
una nuova.

### 4.2 Dashboard stagione attiva

La dashboard della stagione attiva deve contenere:

- codice stagione;
- stato stagione;
- fase corrente;
- date configurabili;
- file quotazioni registrati;
- stato degli step principali;
- pulsanti operativi organizzati per fase;
- eventuali warning su step mancanti.

Tutti i campi data devono essere modificabili dall'admin.

### 4.3 Creazione nuova stagione

Nel tab `Stagioni` deve essere presente un pulsante:

```text
Inizia nuova stagione
```

Alla creazione devono essere richiesti almeno:

- codice stagione, ricavabile automaticamente dall'anno scelto;
- data di inizio stagione.

Le altre date possono essere inserite o modificate successivamente.

Effetti automatici:

- creazione record stagione;
- impostazione della stagione come attiva;
- creazione cartella locale della stagione;
- creazione sottocartelle delle fasi.

## 5. Storage locale stagionale

All'inizio di una stagione deve essere creata una cartella locale:

```text
Stagioni/<codice_stagione>/
```

Per evitare caratteri speciali nel filesystem, il codice stagione va normalizzato
nel nome cartella:

```text
Stagioni/2026-2027/
```

Struttura proposta:

```text
Stagioni/
  2026-2027/
    01_fase_estiva/
      quotazioni/
      backup/
      asta/
      report/
    02_fase_invernale/
      quotazioni/
      backup/
      asta/
      report/
    03_fine_stagione/
      quotazioni/
      backup/
      report/
```

I file collegati a una stagione devono essere salvati nella sottocartella della
fase corretta.

## 6. Naming file

### 6.1 Quotazioni

Fase 1:

```text
Quotazioni iniziali stagione <stagione>
```

Fase 2:

```text
Quotazioni inizio sessione invernale <stagione>
```

Fase 3:

```text
Quotazioni fine stagione <stagione>
```

### 6.2 Backup

Inizio stagione:

```text
Giocatori inizio stagione <stagione>
Fantasquadre inizio stagione <stagione>
```

Pre asta estiva:

```text
Giocatori pre asta estiva <stagione>
Fantasquadre pre asta estiva <stagione>
```

Post asta estiva:

```text
Giocatori post asta estiva <stagione>
Fantasquadre post asta estiva <stagione>
```

Chiusura sessione estiva:

```text
Giocatori chiusura sessione estiva <stagione>
Fantasquadre chiusura sessione estiva <stagione>
Operazioni chiusura sessione estiva <stagione>
```

Inizio sessione invernale:

```text
Giocatori inizio sessione invernale <stagione>
Fantasquadre inizio sessione invernale <stagione>
```

Pre asta invernale:

```text
Giocatori pre asta invernale <stagione>
Fantasquadre pre asta invernale <stagione>
```

Post asta invernale:

```text
Giocatori post asta invernale <stagione>
Fantasquadre post asta invernale <stagione>
```

Chiusura sessione invernale:

```text
Giocatori chiusura sessione invernale <stagione>
Fantasquadre chiusura sessione invernale <stagione>
Operazioni chiusura sessione invernale <stagione>
```

Fine stagione:

```text
Giocatori fine stagione <stagione>
Fantasquadre fine stagione <stagione>
Operazioni fine stagione <stagione>
```

## 7. Workflow fase 1

### 7.1 Inizio stagione

Sezione UI:

```text
Inizio stagione - sessione mercato estiva
```

Step:

1. Registrare o caricare il file:

   ```text
   Quotazioni iniziali stagione <stagione>
   ```

2. Eseguire un bottone unico:

   ```text
   Aggiorna inizio stagione
   ```

3. Il bottone deve aggregare le funzionalita' gia' presenti in menu:

   - `Updates > Quotazioni Update`;
   - `Updates > Serie A Update`.

4. Dopo update completato con successo, creare backup:

   - giocatori;
   - fantasquadre.

### 7.2 Operazioni mercato estive

Durante la fase 1, le operazioni di mercato devono avere contesto default:

```text
sessione estiva <stagione> - <Agosto|Settembre>
```

Il mese deve essere selezionabile tra:

- agosto;
- settembre.

Suggerimento tecnico:

- non sovrascrivere `Operazione.data`, che deve restare una data reale;
- aggiungere campi di contesto come `stagione_id`, `fase_stagione`,
  `periodo_regolamento`, `mese_regolamento`.

### 7.3 Asta estiva

Sezione UI:

```text
Asta estiva
```

Step richiesti:

1. Bottone:

   ```text
   Esporta rose per asta
   ```

   Per ora il bottone puo' essere placeholder o generare un export minimale.
   Il formato definitivo verra' definito in una fase successiva.

2. Bottone:

   ```text
   Backup pre asta estiva
   ```

   Deve esportare giocatori e fantasquadre nella cartella fase 1.

3. Bottone:

   ```text
   Importa asta estiva
   ```

   Per il primo step deve reindirizzare al tab `Mercato`, dove esiste gia' la
   funzione `Importa asta`.

4. Dopo import asta completato senza errori, creare backup:

   - giocatori post asta estiva;
   - fantasquadre post asta estiva.

### 7.4 Chiusura sessione estiva

Bottone:

```text
Chiusura sessione estiva
```

Effetti:

- registrare data chiusura fase 1;
- impostare stato stagione a `campionato in corso`;
- creare backup di:
  - giocatori;
  - fantasquadre;
  - operazioni di mercato della sessione estiva.

## 8. Workflow fase 2

### 8.1 Inizio sessione invernale

Sezione UI:

```text
Sessione invernale di mercato
```

Step:

1. Inserire data inizio fase 2.

2. Registrare o caricare il file:

   ```text
   Quotazioni inizio sessione invernale <stagione>
   ```

3. Bottone:

   ```text
   Aggiorna inizio sessione invernale
   ```

4. Il bottone deve eseguire la funzionalita' gia' presente:

   - `Updates > Complete Update`.

5. Dopo update completato con successo, creare backup:

   - giocatori;
   - fantasquadre.

### 8.2 Operazioni mercato invernali

Durante la fase 2, le operazioni di mercato devono avere contesto default:

```text
sessione invernale <stagione> - <Gennaio|Febbraio>
```

Il mese deve essere selezionabile tra:

- gennaio;
- febbraio.

### 8.3 Asta di riparazione invernale

La sezione asta invernale deve replicare il workflow dell'asta estiva, con naming
coerente:

- esporta rose per asta;
- backup pre asta invernale;
- importa asta invernale;
- backup post asta invernale.

### 8.4 Chiusura sessione invernale

Bottone:

```text
Chiusura sessione invernale
```

Effetti:

- registrare data chiusura fase 2;
- impostare stato stagione a `campionato in corso`;
- creare backup di:
  - giocatori;
  - fantasquadre;
  - operazioni di mercato della sessione invernale.

## 9. Workflow fase 3

### 9.1 Inizio fine stagione

Sezione UI:

```text
Fine stagione
```

Step:

1. Inserire data inizio fase 3.

2. Registrare o caricare il file:

   ```text
   Quotazioni fine stagione <stagione>
   ```

3. Bottone:

   ```text
   Aggiorna fine stagione
   ```

4. Il bottone deve eseguire la funzionalita':

   - `Updates > Complete Update`.

5. Dopo update completato con successo, creare backup:

   - giocatori;
   - fantasquadre.

### 9.2 Svincoli fine contratto

Bottone:

```text
Svincola contratti scaduti
```

Regola:

- individuare i giocatori con `scadenza_contratto` a giugno dell'anno in cui
  finisce la stagione corrente;
- rimuoverli dalla rosa di appartenenza e dalla lista giocatori attivi;
- non accreditare FM alla fantasquadra proprietaria;
- registrare operazioni/audit dedicate agli svincoli di fine contratto.

Contesto default per queste operazioni:

```text
Fine stagione <stagione> - <Maggio|Giugno>
```

Il mese deve essere selezionabile tra:

- maggio;
- giugno.

Nota tecnica:

- questo flusso non deve riusare lo svincolo ordinario se lo svincolo ordinario
  accredita il valore di svincolo;
- serve un comando dedicato, ad esempio `SvincolaFineContrattoCommand`;
- l'operazione deve essere auditabile tramite `semantic_undo_log`.

## 10. Modello dati proposto

### 10.1 Tabella `stagioni`

Campi proposti:

- `id`;
- `codice`;
- `anno_inizio`;
- `anno_fine`;
- `data_inizio`;
- `data_fine`;
- `stato`;
- `fase_corrente`;
- `storage_path`;
- `created_at`;
- `updated_at`;
- `deleted`.

Vincoli:

- una sola stagione attiva alla volta;
- `codice` univoco.

### 10.2 Tabella `stagione_fasi`

Campi proposti:

- `id`;
- `stagione_id`;
- `codice_fase`;
- `nome`;
- `data_inizio`;
- `data_fine`;
- `stato`;
- `asta_data_inizio`;
- `asta_data_fine`;
- `created_at`;
- `updated_at`.

Valori `codice_fase`:

- `fase_1_estiva`;
- `fase_2_invernale`;
- `fase_3_fine_stagione`.

### 10.3 Tabella `stagione_files`

Serve a tracciare i file caricati o generati.

Campi proposti:

- `id`;
- `stagione_id`;
- `fase_id`;
- `tipo_file`;
- `nome_logico`;
- `path`;
- `created_at`;
- `note`.

Esempi `tipo_file`:

- `quotazioni_iniziali`;
- `quotazioni_invernali`;
- `quotazioni_fine_stagione`;
- `backup_giocatori`;
- `backup_fantasquadre`;
- `backup_operazioni`;
- `export_asta`.

### 10.4 Tabella `stagione_step_log`

Serve a tracciare gli step eseguiti dalla dashboard stagione.

Campi proposti:

- `id`;
- `stagione_id`;
- `fase_id`;
- `step_key`;
- `status`;
- `started_at`;
- `completed_at`;
- `error_message`;
- `metadata_json`.

Esempi `step_key`:

- `crea_stagione`;
- `carica_quotazioni_iniziali`;
- `aggiorna_inizio_stagione`;
- `backup_pre_asta_estiva`;
- `importa_asta_estiva`;
- `chiudi_sessione_estiva`;
- `aggiorna_inizio_sessione_invernale`;
- `chiudi_sessione_invernale`;
- `aggiorna_fine_stagione`;
- `svincola_contratti_scaduti`.

### 10.5 Estensione `operazioni`

Aggiungere contesto stagionale alle operazioni.

Campi proposti:

- `stagione_id`;
- `fase_stagione`;
- `periodo_regolamento`;
- `mese_regolamento`.

Nota:

- `data` resta una data reale;
- i nuovi campi servono per storico, dashboard, report e filtri.

## 11. Architettura applicativa proposta

### 11.1 Service layer

Nuovo service:

```text
services/stagione_service.py
```

Responsabilita':

- creare stagione;
- aggiornare date e metadati;
- calcolare fase corrente;
- registrare file stagionali;
- creare cartelle;
- eseguire step dashboard;
- orchestrare update esistenti;
- orchestrare backup;
- chiudere fasi;
- eseguire svincoli fine contratto.

### 11.2 Command/DTO

Comandi proposti:

- `CreateStagioneCommand`;
- `UpdateStagioneDatesCommand`;
- `RegisterSeasonFileCommand`;
- `RunSeasonStartUpdateCommand`;
- `RunWinterStartUpdateCommand`;
- `RunEndSeasonUpdateCommand`;
- `CloseSummerSessionCommand`;
- `CloseWinterSessionCommand`;
- `ReleaseExpiredContractsCommand`.

DTO principali:

- `StagioneDTO`;
- `StagioneDashboardDTO`;
- `StagioneFaseDTO`;
- `StagioneFileDTO`;
- `StagioneStepDTO`.

### 11.3 Widget layer

Nuovo widget:

```text
widgets/stagioni_widget.py
```

Responsabilita':

- tab `Stagioni`;
- dashboard stagione attiva;
- sezioni per fase;
- pulsanti step;
- stato visuale degli step;
- form edit date;
- redirect verso tab `Mercato` per import asta.

### 11.4 Integrazione con update esistenti

Le funzioni update oggi sono metodi di `MainWindow`:

- `_complete_update`;
- `_quotazioni_update`;
- `_serie_a_update`;
- `_upload_quotazioni`.

Per integrarle bene con `Stagioni`, conviene estrarle progressivamente in un
service dedicato:

```text
services/quotazioni_service.py
```

Il menu `Updates` e il tab `Stagioni` dovrebbero chiamare lo stesso service,
evitando duplicazione logica.

### 11.5 Integrazione con backup esistenti

`DataManagerUI` oggi gestisce backup manuali da UI.

Per gli automatismi stagionali serve estrarre la logica file in un service
riusabile:

```text
services/backup_service.py
```

Il service deve permettere:

- export di una o piu' tabelle;
- path destinazione esplicito;
- nome file esplicito;
- ritorno esito e path creati.

### 11.6 Integrazione con Mercato

Il tab `Mercato` deve ricevere il contesto stagione corrente.

Effetti:

- default periodo operazione;
- default fase;
- eventuale filtro mese selezionabile in base alla fase;
- salvataggio `stagione_id` e campi contesto su `Operazione`;
- storico filtrabile per stagione/fase.

Per import asta, nel primo step e' sufficiente:

- pulsante nel tab `Stagioni`;
- switch automatico al tab `Mercato`;
- eventualmente messaggio guida.

## 12. Persistenza e migrazioni

Ogni nuova tabella o campo deve avere:

- migrazione SQLite in `migrations/`;
- migrazione Supabase in `supabase/migrations/`, se il dato deve essere
  recuperabile anche da remoto;
- aggiornamento seed/export Supabase se necessario;
- test di migrazione.

Le stagioni sono dati applicativi permanenti, quindi devono essere incluse nella
persistenza remota Supabase.

## 13. Semantic undo e audit

Gli step stagionali che modificano dati devono essere auditabili.

Operazioni da includere:

- update inizio stagione;
- update inizio sessione invernale;
- update fine stagione;
- import asta, quando sara' integrato direttamente;
- svincoli fine contratto.

Per gli svincoli fine contratto serve snapshot before/after dei giocatori
toccati e delle operazioni generate.

## 14. Suggerimenti tecnici

1. Non introdurre la feature come grande blocco unico.
   Conviene procedere per step piccoli e verificabili.

2. Non duplicare la logica update presente in `MainWindow`.
   Prima estrarre un service riusabile, poi collegarlo al tab `Stagioni`.

3. Non usare stringhe descrittive al posto di date reali.
   Conservare `Operazione.data` come data e aggiungere campi contesto.

4. Rendere i backup stagionali deterministici.
   Il service deve sapere sempre dove salvare e con quale nome.

5. Tracciare gli step eseguiti.
   La dashboard deve poter mostrare cosa e' gia' stato fatto e cosa manca.

6. Rendere la cartella `Stagioni/` configurabile in futuro.
   Per ora puo' stare nella root progetto, ma a regime potrebbe diventare una
   cartella dati utente.

7. Aggiungere test fin dall'inizio.
   Le parti piu' critiche sono:
   - calcolo fase corrente;
   - naming stagione;
   - creazione cartelle;
   - backup automatici;
   - svincolo fine contratto senza accredito FM.

## 15. Roadmap implementativa consigliata

### Step 1: fondazioni dominio. IMPLEMENTATO

- Aggiungere modelli `Stagione`, `StagioneFase`, `StagioneFile`,
  `StagioneStepLog`.
- Aggiungere migrazioni SQLite e Supabase.
- Aggiungere service minimo `StagioneService`.
- Aggiungere test su creazione stagione, codice stagione e fasi.

Stato implementazione:

- aggiunti modelli SQLAlchemy in `models.py`;
- aggiunta migrazione SQLite `008_stagioni`;
- aggiunta migrazione Supabase `20260715000100_stagioni.sql`;
- aggiunto `services/stagione_service.py`;
- aggiunti test `tests/test_stagione_service.py`;
- aggiornati seed exporter e snapshot sync per includere le nuove tabelle.

### Step 2: tab Stagioni. IMPLEMENTATO

- Creare `StagioniWidget`.
- Aggiungere tab `Stagioni` in `MainWindow`.
- Mostrare dashboard stagione attiva.
- Consentire creazione nuova stagione.
- Consentire modifica date fasi/aste.
- Creare cartelle stagionali.

Stato implementazione:

- aggiunto `widgets/stagioni_widget.py`;
- aggiunto tab `Stagioni` in `MainWindow`;
- se non esiste una stagione attiva, il tab mostra il form `Inizia nuova stagione`;
- se esiste una stagione attiva, il tab mostra dashboard con stato, fase corrente,
  cartella storage e date;
- implementata modifica date stagione, date fasi e date aste;
- la creazione stagione usa `StagioneService` e crea la struttura cartelle.

### Step 3: backup service. IMPLEMENTATO

- Estrarre logica backup da `DataManagerUI`.
- Consentire export programmato verso path esplicito.
- Collegare i primi pulsanti backup nel tab `Stagioni`.

Stato implementazione:

- aggiunto `services/backup_service.py`;
- `DataManager.export_data` delega al nuovo `BackupService`;
- aggiunti backup stagionali deterministici per fase;
- i backup stagionali vengono salvati nella sottocartella `backup` della fase;
- ogni file generato viene registrato in `stagione_files`;
- aggiunti pulsanti backup nel tab `Stagioni` per fase estiva, fase invernale e
  fine stagione;
- aggiunti test `tests/test_backup_service.py`.

### Step 4: quotazioni service. IMPLEMENTATO

- Estrarre update quotazioni/Serie A/complete update da `MainWindow`.
- Far chiamare lo stesso service da menu `Updates` e tab `Stagioni`.
- Implementare:
  - update inizio stagione;
  - update inizio sessione invernale;
  - update fine stagione.

Stato implementazione:

- aggiunto `services/quotazioni_service.py`;
- i comandi menu `Complete Update`, `Quotazioni Update` e `Serie A Update`
  chiamano il nuovo service;
- il tab `Stagioni` espone pulsanti update nella fase corretta;
- `Aggiorna inizio stagione` esegue update quotazioni + presenza Serie A;
- `Aggiorna inizio sessione invernale` esegue complete update;
- `Aggiorna fine stagione` esegue complete update;
- dopo ogni update stagionale viene creato il backup coerente della fase;
- aggiunti test `tests/test_quotazioni_service.py`.

### Step 5: contesto mercato. IMPLEMENTATO

- Aggiungere campi stagionali a `Operazione`.
- Far leggere al tab `Mercato` la stagione attiva.
- Applicare default fase/periodo/mese in base alla fase corrente.
- Aggiornare storico operazioni con info stagione/fase.

Stato implementazione:

- aggiunti a `Operazione` i campi `stagione_id`, `fase_stagione`,
  `periodo_regolamento` e `mese_regolamento`;
- aggiunta migrazione SQLite `009_operation_season_context`;
- aggiunta migrazione Supabase `20260715000200_operation_season_context.sql`;
- il seed export Supabase include le nuove colonne di contesto;
- `MercatoWidget` legge la stagione attiva tramite `StagioneService`;
- `OperazioneRepository` applica il contesto in modo centralizzato a tutte le
  operazioni registrate;
- le operazioni fuori sessione vengono agganciate all'ultima sessione di mercato
  chiusa, come da decisione confermata;
- lo storico operazioni mostra il contesto regolamentare quando presente;
- aggiunti test minimi sul calcolo del contesto e sulla persistenza in
  operazione.

### Step 6: aste stagionali. IMPLEMENTATO

- Aggiungere pulsanti:
  - esporta rose per asta;
  - importa asta estiva;
  - importa asta invernale.
- Per il primo step, `Importa asta` puo' solo portare al tab `Mercato`.
- In seguito, integrare direttamente il flusso asta nel tab `Stagioni`.

Stato implementazione:

- aggiunto `BackupService.export_rosters_for_asta`;
- il tab `Stagioni` espone i pulsanti asta nelle fasi estiva e invernale;
- `Esporta rose per asta` genera un JSON stagionale nella cartella della fase;
- il file generato viene registrato in `stagione_files`;
- i pulsanti `Importa asta` portano al tab `Mercato`, mantenendo il flusso di
  import esistente come sorgente operativa;
- aggiunto test sul file di export rose e sulla registrazione in archivio.

### Step 7: fine stagione. IMPLEMENTATO

- Implementare svincolo fine contratto.
- Assicurare assenza di accredito FM.
- Registrare audit/semantic undo.
- Generare backup operazioni fine stagione.

Stato implementazione:

- aggiunto comando `SvincoloFineContrattoCommand`;
- aggiunto metodo applicativo `MercatoService.svincola_fine_contratto`;
- aggiunto flusso dedicato in `OperazioneRepository`, separato dallo
  `svincolo` ordinario;
- il flusso crea operazioni `svincolo fine contratto`, senza accredito FM;
- le operazioni vengono registrate con contesto
  `Fine stagione <stagione> - <Maggio|Giugno>`;
- lo storico operazioni mostra una card dedicata con indicazione
  `Nessun accredito FM`;
- `semantic_undo_log` registra l'operazione e l'undo ricrea i giocatori
  svincolati senza modificare il saldo FM;
- il tab `Stagioni` espone il bottone `Svincola contratti scaduti` nella fase
  fine stagione, con selezione mese maggio/giugno;
- dopo lo svincolo viene creato il backup `fine_stagione`;
- i dati storici con la vecchia convenzione sono migrati a `30 giugno`;
- aggiunti test di business rule e semantic undo.

## 16. Decisioni e questioni aperte

### 16.1 Questioni ancora aperte

1. Formato asta definitivo.
   Esiste un primo export JSON operativo per le rose, ma resta da definire il
   formato definitivo da usare quando il flusso di import asta verra' portato
   direttamente dentro il tab `Stagioni`.

### 16.2 Decisioni confermate

1. Cartella `Stagioni/`.
   Per ora resta nella root del progetto.

2. Operazioni fuori sessione.
   Sono consentite anche quando lo stato e' `campionato in corso`.
   Devono essere datate nel contesto regolamentare dell'ultimo mese dell'ultima
   sessione di mercato chiusa.

   Esempio:
   - se l'ultima sessione chiusa e' quella estiva, il contesto default resta
     `sessione estiva <stagione> - Settembre`;
   - se l'ultima sessione chiusa e' quella invernale, il contesto default resta
     `sessione invernale <stagione> - Febbraio`.

3. Chiusura stagione.
   La chiusura finale marca soltanto la stagione come `chiusa`; non blocca
   automaticamente ogni modifica.

4. Import asta.
   Nel primo step viene mantenuto il redirect al tab `Mercato`; in futuro il
   flusso andra' probabilmente portato dentro `Stagioni`.
