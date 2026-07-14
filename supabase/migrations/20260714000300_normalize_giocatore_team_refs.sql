-- Normalize player ownership/loan references while keeping legacy text columns
-- for UI compatibility and migration safety.

alter table public.giocatori
    add column if not exists fantasquadra_id bigint references public.fantasquadre(id);

alter table public.giocatori
    add column if not exists prestito_a_fantasquadra_id bigint references public.fantasquadre(id);

update public.giocatori g
set fantasquadra_id = f.id
from public.fantasquadre f
where g.fantasquadra_id is null
  and g.squadra is not null
  and btrim(g.squadra) <> ''
  and f.nome = g.squadra
  and coalesce(f.deleted, false) = false;

update public.giocatori g
set prestito_a_fantasquadra_id = f.id
from public.fantasquadre f
where g.prestito_a_fantasquadra_id is null
  and g.in_prestito_a is not null
  and btrim(g.in_prestito_a) <> ''
  and f.nome = g.in_prestito_a
  and coalesce(f.deleted, false) = false;

create index if not exists idx_giocatori_fantasquadra_id
    on public.giocatori(fantasquadra_id);

create index if not exists idx_giocatori_prestito_a_fantasquadra_id
    on public.giocatori(prestito_a_fantasquadra_id);
