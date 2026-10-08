# GH Pages + Supabase Free — Login + Normal Chat (journey)

Web = GH Pages (static) — **free** `https://arpitsingh40.github.io/unified-platform/`
Auth + DB + chat = **Supabase Free** (50k MAU, 500MB DB, 500k Function calls) — **$0**
LLM = DeepSeek (free $5 credit ~ 1k chats) via Edge Function — **$0** for prototype
Windows app = FORGE.exe — **must for execution** (agent browser + local FS/shell, only LLM leaves device)

> This doc makes web do **CAN free: login + signup + simple `journey/start + journey/message` (1 LLM call) + history per user**. Desktop stays local-first.

---

## 1) What you get

| Page | Auth | Chat | Where code lives |
|---|---|---|---|
| `https://arpitsingh40.github.io/unified-platform/` | Supabase Auth (email/password) via `@supabase/supabase-js` | `supabase.functions.invoke('chat')` → DeepSeek → stream, saves to `conversations/messages` (RLS per user) | `frontend/src/lib/supabase.ts`, `AuthPage.jsx`, `JourneyPage.jsx` |
| `https://arpitsingh40.github.io/unified-platform/#/auth` | same | same — history reloads on `/app` | `App.tsx` (web: `getSession()` not `business-os`) |
| FORGE.exe | local `business-os :8000` + `Bearer` fallback | local `business-os + engine.py + 12 agents` | `business-os/`, `desktop/src-tauri` |

If `VITE_SUPABASE_URL/ANON_KEY` are empty, web gracefully falls back to demo (no DB) + `Download FORGE` CTA.

---

## 2) Create Supabase project (once, 3 min)

1. https://supabase.com → New project (Free) → pick region → wait for DB to be ready.
2. Project Settings → API → copy:
   - `Project URL` → `https://<id>.supabase.co`
   - `anon public` → `ey...`
3. Authentication → Providers → Email → **Enable Confirm email** = your call (if ON, signup says "check email" then login).

---

## 3) Run SQL (once)

Project → SQL Editor → New query → paste `supabase/sql/001_tables.sql` → Run.

This creates:

```sql
conversations (id uuid, user_id uuid→auth.users, objective text, title, created_at, updated_at)
messages (id bigserial, conversation_id→conversations, role user|assistant, content text, created_at)
-- RLS: each user can only select/insert their own conversations + messages
-- Trigger: touch_conversation() keeps updated_at fresh
```

Verify: Table Editor should show both tables.

---

## 4) Deploy Edge Function `chat` (once)

In Supabase Dashboard → Edge Functions → Create function `chat` → replace contents with `supabase/functions/chat/index.ts` → Deploy.

Then set secrets (Dashboard → Edge Functions → `chat` → Secrets or `supabase secrets set` if using CLI):

```
DEEPSEEK_API_KEY=sk-...      # required — your DeepSeek key
DEEPSEEK_MODEL=deepseek-chat # optional, default deepseek-chat
```

The function already has CORS + JWT check (`Authorization: Bearer <user_jwt>`). Verify:

```bash
curl -X POST 'https://<id>.supabase.co/functions/v1/chat' \
  -H "Authorization: Bearer <USER_JWT>" \
  -H apikey:<ANON_KEY> -H Content-Type:application/json \
  -d '{"message":"hello, test","objective":"test"}'
# → {"reply":"...","conversation_id":"...","usage":{...}}
```

If you use Supabase CLI locally:

```bash
supabase login
supabase link --project-ref <id>
supabase functions deploy chat --no-verify-jwt=false
supabase secrets set DEEPSEEK_API_KEY=sk-... DEEPSEEK_MODEL=deepseek-chat
```

---

## 5) Wire GH Pages (2 secrets + workflow)

Code already on `main`: `VITE_TARGET=web` builds `frontend/build-web` with `base: /unified-platform/` + `HashRouter`. The deploy workflow needs 2 repo secrets.

**Repo Settings → Secrets and variables → Actions → New repository secret:**

- `VITE_SUPABASE_URL` = `https://<id>.supabase.co`
- `VITE_SUPABASE_ANON_KEY` = `ey...` (anon public key — safe to expose, RLS protects data)

**Then add the Pages workflow** (GH UI — `workflow` scope is blocked via `gh` CLI on this token):

1. On `https://github.com/arpitsingh40/unified-platform` → Add file → `.github/workflows/deploy-landing.yml` → paste:

```yaml
name: Deploy landing to GitHub Pages
on:
  push:
    branches: [main]
    paths: [frontend/**, .github/workflows/deploy-landing.yml]
  workflow_dispatch:
permissions: { contents: read, pages: write, id-token: write }
concurrency: { group: pages, cancel-in-progress: false }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
        env:
          VITE_TARGET: web
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}
      - run: |
          touch frontend/build-web/.nojekyll
          cp frontend/build-web/index.html frontend/build-web/404.html
      - uses: actions/upload-pages-artifact@v3
        with: { path: frontend/build-web }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: ${{ steps.deployment.outputs.page_url }}}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

2. Settings → Pages → Source: **GitHub Actions** (or keep `gh-pages` branch while migrating).

After the next push to `main`, the site builds with Supabase env and chat works. Until then, the current live `gh-pages` build (`c5ad601`) is download-only; after workflow runs, login+chat light up.

---

## 6) Verify

1. Open `https://arpitsingh40.github.io/unified-platform/#/auth` → Sign up → (if confirm email ON, check inbox, then Sign in).
2. Go to `/#/app` → type objective → **Start** → should create a conversation + get assistant reply (Edge Function) → reload → history persists.
3. Check Supabase → Table Editor → `conversations` + `messages` rows appear for your `auth.users` id only.

If chat says "Edge Function not configured": set `DEEPSEEK_API_KEY` in Supabase secrets. If "Missing Authorization": re-login (JWT expired). Free quotas: 50k auth users, 500MB DB ~ 500k messages, 500k function calls.

---

## 7) Desktop vs Web

- **Web chat** = 1 DeepSeek call, no `engine.py` rolling/hypotheses/agents — perfect for `discuss/plan`.
- **Windows FORGE.exe** = full `engine.py` + 12 agents + `agent-browser` + `~/Documents/FORGE` FS/shell (sandboxed), hotkey `Ctrl+Shift+F`, tray.

Keep `frontend/src/lib/supabase.ts:isSupabaseConfigured` — desktop/dev ignore Supabase; web uses it only when configured.

---

## Files

- `frontend/src/lib/supabase.ts` — client + types
- `frontend/src/pages/AuthPage.jsx` — web: `supabase.auth`, desktop: `business-os`
- `frontend/src/pages/JourneyPage.jsx` — web: `supabase.from('conversations/messages')` + `functions.invoke('chat')`, desktop: `api.post('/journey/*')`
- `frontend/src/App.tsx` — web: `supabase.auth.getSession()/signOut()`, GH Pages `HashRouter`
- `frontend/vite.config.ts` — `VITE_TARGET=web` → `outDir: build-web + base: /unified-platform/`
- `supabase/sql/001_tables.sql` — schema + RLS
- `supabase/functions/chat/index.ts` — Edge Function (Deno)
