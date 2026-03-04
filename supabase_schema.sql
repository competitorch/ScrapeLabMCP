-- ScrapeLab MCP — Supabase Schema
-- Run this in the Supabase SQL Editor

-- 1. Recipes table
create table public.recipes (
  id bigserial primary key,
  user_id uuid,
  site_pattern text not null,
  site_name text not null,
  scrape_level int default 1,
  prompt text,
  script text,
  schema jsonb,
  config jsonb default '{}'::jsonb,
  is_public boolean default false,
  version int default 1,
  times_used int default 0,
  success_rate real default 0.0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- 2. Recipe history (auto-populated by trigger)
create table public.recipe_history (
  id bigserial primary key,
  recipe_id bigint references public.recipes on delete cascade,
  version int not null,
  prompt text,
  script text,
  schema jsonb,
  config jsonb,
  changed_at timestamptz default now(),
  change_note text
);

-- 3. Indexes
create index idx_recipes_site_pattern on public.recipes (site_pattern);
create index idx_recipes_is_public on public.recipes (is_public);
create index idx_recipe_history_recipe_id on public.recipe_history (recipe_id);

-- 4. RLS (enabled but permissive for now — service_role bypasses RLS)
alter table public.recipes enable row level security;
alter table public.recipe_history enable row level security;

create policy "Public recipes are viewable by everyone"
  on public.recipes for select
  using (is_public = true);

create policy "Authenticated users can manage own recipes"
  on public.recipes for all
  using (auth.uid() = user_id);

create policy "History viewable by recipe owner"
  on public.recipe_history for select
  using (
    exists (
      select 1 from public.recipes
      where recipes.id = recipe_history.recipe_id
      and (recipes.is_public = true or recipes.user_id = auth.uid())
    )
  );

-- 5. Auto-update updated_at on recipe change
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger recipes_updated_at
  before update on public.recipes
  for each row execute function update_updated_at();

-- 6. Auto-save history before update + bump version
create or replace function save_recipe_history()
returns trigger as $$
begin
  -- Only save history if content actually changed
  if old.prompt is distinct from new.prompt
     or old.script is distinct from new.script
     or old.schema is distinct from new.schema
     or old.config is distinct from new.config then
    insert into public.recipe_history (recipe_id, version, prompt, script, schema, config)
    values (old.id, old.version, old.prompt, old.script, old.schema, old.config);
    new.version = old.version + 1;
  end if;
  return new;
end;
$$ language plpgsql;

create trigger recipes_history_trigger
  before update on public.recipes
  for each row execute function save_recipe_history();
