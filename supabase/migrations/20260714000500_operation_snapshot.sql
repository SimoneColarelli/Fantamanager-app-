-- Replace operation-specific player snapshots with a uniform operation snapshot.
-- The legacy giocatori_snapshot column is left in place for existing projects,
-- but new application code writes and reads operation_snapshot.

alter table public.operazioni
    add column if not exists operation_snapshot text;

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'operazioni'
          and column_name = 'giocatori_snapshot'
    ) then
        execute $sql$
            update public.operazioni
            set operation_snapshot = jsonb_build_object(
                'schema_version', 1,
                'source', 'legacy_migration',
                'tipo_operazione', tipo_operazione,
                'data', data,
                'clausole', coalesce(clausole, ''),
                'conguaglio', coalesce(conguaglio, 0),
                'conguaglio_da_id', conguaglio_da_id,
                'fantasquadre', jsonb_build_object(
                    'a', jsonb_build_object('id', fantasquadra_a_id),
                    'b', jsonb_build_object('id', fantasquadra_b_id)
                ),
                'giocatori',
                    case
                        when giocatori_snapshot is null or btrim(giocatori_snapshot) = ''
                            then '[]'::jsonb
                        else giocatori_snapshot::jsonb
                    end
            )::text
            where operation_snapshot is null
        $sql$;
    end if;
end $$;
