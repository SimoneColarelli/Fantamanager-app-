-- Move contract/loan end defaults from July 1 to June 30.

update public.giocatori
set scadenza_contratto = make_date(extract(year from scadenza_contratto)::int, 6, 30)
where scadenza_contratto is not null
  and extract(month from scadenza_contratto) = 7
  and extract(day from scadenza_contratto) = 1;

update public.giocatori
set fine_prestito = make_date(extract(year from fine_prestito)::int, 6, 30)
where fine_prestito is not null
  and extract(month from fine_prestito) = 7
  and extract(day from fine_prestito) = 1;

update public.operazioni
set operation_snapshot = replace(operation_snapshot, '-07-01', '-06-30')
where operation_snapshot like '%-07-01%';

update public.semantic_undo_log
set before_snapshot = replace(before_snapshot, '-07-01', '-06-30')
where before_snapshot like '%-07-01%';

update public.semantic_undo_log
set after_snapshot = replace(after_snapshot, '-07-01', '-06-30')
where after_snapshot like '%-07-01%';

update public.semantic_undo_log
set inverse_payload = replace(inverse_payload, '-07-01', '-06-30')
where inverse_payload like '%-07-01%';
