-- Store market economic values as integer FM amounts.

alter table if exists public.giocatori
    alter column spesa type integer using round(spesa)::integer,
    alter column valore_svincolo type integer using round(valore_svincolo)::integer;
