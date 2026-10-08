-- Supabase Free: conversations + messages with RLS — paste in SQL Editor
-- Run once after creating the project. No extra cost.

extension if not exists "uuid-ossp" schema public;

create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  objective text not null default '',
  title text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.messages (
  id bigserial primary key,
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  role text not null check (role in ('user','assistant')),
  content text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_conv_user on public.conversations(user_id, created_at desc);
create index if not exists idx_msg_conv on public.messages(conversation_id, id);

alter table public.conversations enable row level security;
alter table public.messages enable row level security;

-- Users can only see/manage their own conversations/messages
drop policy if exists "own conv" on public.conversations;
create policy "own conv" on public.conversations for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own msg select" on public.messages;
create policy "own msg select" on public.messages for select using (
  exists (select 1 from public.conversations c where c.id = conversation_id and c.user_id = auth.uid())
);
drop policy if exists "own msg insert" on public.messages;
create policy "own msg insert" on public.messages for insert with check (
  exists (select 1 from public.conversations c where c.id = conversation_id and c.user_id = auth.uid())
);
drop policy if exists "own msg delete" on public.messages;
create policy "own msg delete" on public.messages for delete using (
  exists (select 1 from public.conversations c where c.id = conversation_id and c.user_id = auth.uid())
);

-- Keep updated_at fresh
create or replace function public.touch_conversation() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;
drop trigger if exists trg_touch_conv on public.conversations;
create trigger trg_touch_conv before update on public.conversations for each row execute function public.touch_conversation();
