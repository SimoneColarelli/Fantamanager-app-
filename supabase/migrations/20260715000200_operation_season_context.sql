-- Add season context metadata to market operations.

alter table public.operazioni
    add column if not exists stagione_id bigint references public.stagioni(id),
    add column if not exists fase_stagione text,
    add column if not exists periodo_regolamento text,
    add column if not exists mese_regolamento text;

create index if not exists idx_operazioni_stagione_id
    on public.operazioni(stagione_id);

create index if not exists idx_operazioni_fase_stagione
    on public.operazioni(fase_stagione);
