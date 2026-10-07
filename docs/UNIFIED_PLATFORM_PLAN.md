# UNIFIED PLATFORM — Idea → Business → 10×/Year

> **One-line pitch:** Founder types one idea → platform builds the entire business (brand, catalog, storefront, payments, org, agents, automations) in minutes and then runs autonomous growth loops that compound to 10× YoY.

**Source inventories:** `ari/` (WASM enterprise kernel), `Smartdecision-main/` (Autonomous Executive OS), `BusinessFactory/` (DRIFT scaffolder). This plan merges them without rewriting languages.

---

## 1. What each codebase actually is (honest inventory)

| Repo | What it is | Strength to keep | Weakness to fix in merge |
|---|---|---|---|
| **ARI** (`ari/`) | Rust WASM Component Model kernel: `runtime/src/host` (governance, auth, tenancy, secrets, audit, memory, verification, approval, idempotency, rate limit, telemetry) + `cli` (`ari build/push/deploy/run`) + `spec/agent-spec.yaml` + `sdk/*` | Only repo that is **enterprise-safe**: JWT HS256, per-org vault (AES-GCM random nonce), `assert_tenant`, governance DB, append-only audit, HMAC webhooks, idempotency, OTEL. Already `cargo build` green (ENTERPRISE_GAP 12/12 closed). | Not a product — no founder UX, no storefront, no growth logic |
| **SmartDecigen** (`Smartdecision-main/`) | FastAPI + React + MongoDB **Autonomous Executive Organization**: `CONSTITUTION.md` (12 principles), Genesis Engine (twin → mission → org → capabilities), 12 agents, `business_os.py` (7 processes + cycle), `business_system.py` (16-function graph + signal scan + root-cause walker), `business_taxonomy.py` (167 books), `execution/` (1403 tools via Composio/MCP), `lenses`, `okr_engine`, `decision_brain`, audit/trace | Only repo with a **brain**: genesis, system model, agents, execution, learning, founder inbox. Real ontology & constitution. | Python monolith, Mongo-coupled, no WASM isolation, storefront is external, store not productized |
| **BusinessFactory** (`BusinessFactory/`) | Next.js 14.2 scaffolder: `DRIFT` demo (24 SKUs, 3 drops, catalog/cart/checkout/admin), `src/lib/factory.ts` (`buildBusiness(idea)`), `src/lib/catalog.ts`, `LAUNCH_KIT.md` | Only repo that **ships a revenue-ready store in <15 min** (`/`, `/catalog`, `/product/[id]`, `/cart`, `/checkout`, `/admin`, `/api/checkout`). Factory abstraction is the right wedge. | Toy: 2 hardcoded templates, in-memory orders, no DB, no payments, no auth, no Genesis link, no agents |

**Key finding:** `ari/CONSOLIDATION_PLAN.md` already plans `ARI = kernel, SmartDecigen = Business OS, sales-agent = vertical` with SmartDecigen calling `POST /api/v1/invoke` with `AuthenticatedUser.org_id`. The merge should **honor this** — don't collapse Rust into Python.

---

## 2. Target architecture — one constitution, three layers, one org_id

```
┌─────────────────────────────────────────────────────────────────┐
│  CONSTITUTION.md (single source of truth, from SmartDecigen)    │
│  12 principles → governs every layer                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER A — KERNEL  (ARI, Rust/WASM)                             │
│  runtime/src/host: auth, tenancy, governance(State+spend),      │
│  secrets(vault), audit(trace_id), memory(encrypted),            │
│  verification(HMAC webhook), approval, idempotency, rate limit, │
│  capabilities(CapabilityRegistry), OTEL                         │
│  cli: ari build/push/deploy/run  ·  spec/agent-spec.yaml        │
│  Serves: POST /api/v1/invoke  (Bearer, Idempotency-Key)         │
│  Guarantees: tenant isolation, spend caps, audit trail         │
└────────────────────────┬────────────────────────────────────────┘
                         │  HTTP+JWT  (AuthenticatedUser.org_id)
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER B — BUSINESS OS  (SmartDecigen, Python/FastAPI)         │
│  genesis.py: extract_twin → generate_mission →                  │
│            generate_organization → map_capabilities             │
│  business_system.py: 16-function graph, signal scan,            │
│            causal walker, opportunity scanner                    │
│  agents.py: 12 agents (strategy/growth/sales/marketing/… )     │
│  business_os.py: 7 processes + business_cycle() + approvals     │
│  execution/: dispatcher, MCP/Composio (1403 tools), collectors  │
│  MongoDB: orgs, goal_threads, agents, os_runs, approvals, inbox│
│  Calls: LAYER A for every tool execution needing trust          │
│  Calls: LAYER C for storefront provisioning & revenue hooks     │
└────────────────────────┬────────────────────────────────────────┘
                         │  API + events
┌────────────────────────▼────────────────────────────────────────┐
│  LAYER C — STOREFRONT FACTORY  (BusinessFactory, Next.js 14)   │
│  Generalized: src/lib/catalog.ts → src/lib/blueprints/*        │
│  Routes: / /catalog /product/[id] /cart /checkout /admin       │
│  Checkout: Razorpay/UPI + Supabase orders (not in-memory)       │
│  Factory API: POST /factory/build {idea} → live store           │
│  Admin: revenue/AOV/valuation + agent status + growth board     │
│  Emits: order.created, cart.abandoned → LAYER B agents         │
└─────────────────────────────────────────────────────────────────┘
         All layers share: org_id, trace_id, Authority L0-L5
```

**Non-negotiables (from Constitution):** capability abstraction, evidence-first learning, authority gradient L0-L5, traceability, reversibility, human override. Every agent decision carries trace_id from Layer A audit.

---

## 3. Monorepo shape (final)

```
unified-platform/                 # new repo (or rename Smartdecision-main)
├── CONSTITUTION.md               # copied verbatim from SmartDecigen (frozen)
├── README.md                     # Idea → 10× story + 5-min quickstart
├── docker-compose.yml            # postgres + mongo + redis + ari + business-os + factory
│
├── kernel/                       # ← from ari/ (keep Rust)
│   ├── runtime/src/host/         #   (no renames — just moved)
│   │   ├── src/{auth,tenancy,audit,secrets,governance,memory,
│   │   │        capabilities,verification,approval,identity,
│   │   │        runtime,metrics,idempotency,telemetry}.rs
│   │   ├── migrations/{001_initial,002_idempotency}.sql
│   │   └── wit/ari.wit
│   ├── cli/                      # ari build/push/deploy/run
│   ├── sdk/{python,typescript}/
│   ├── spec/agent-spec.yaml
│   └── examples/sales-agent/
│
├── business-os/                  # ← from Smartdecision-main/backend
│   ├── server.py                 # FastAPI (all 30+ routers)
│   ├── genesis.py                # 4-step genesis (extract→mission→org→capabilities)
│   ├── business_system.py        # 16-function graph
│   ├── business_taxonomy.py      # 167-book failure taxonomy
│   ├── business_os.py            # 7 processes + business_cycle
│   ├── agents.py                 # 12 agents + AGENT_DEFINITIONS
│   ├── execution/                # dispatcher + Composio + verification
│   ├── ontology/                 # Mission, Goal, Capability, Trace
│   ├── lenses/ knowledge/ salaar/
│   ├── requirements.txt
│   └── tests/
│
├── factory/                      # ← from BusinessFactory (generalized)
│   ├── src/
│   │   ├── app/{page,catalog,product/[id],cart,checkout,admin,api/checkout}
│   │   ├── lib/{catalog,cart,factory,blueprints/*,payments,db}
│   │   └── components/{Header,ProductCard,GrowthBoard,AgentStatus}
│   ├── blueprints/               # idea → blueprint registry (replaces 2-template factory.ts)
│   │   ├── fashion.ts  beauty.ts  food.ts  digital.ts  generic.ts
│   │   └── index.ts              # LLM fallback when no template matches
│   ├── next.config.js  tailwind.config.js  tsconfig.json
│   └── package.json
│
├── frontend/                     # ← from Smartdecision-main/frontend (control plane UI)
│   └── src/pages/{Genesis,Dashboard,Growth,Agents,Approvals,Audit}
│
├── deploy/ {fly.toml,koyeb.yaml,render.yaml,Dockerfile,vercel.json}
└── docs/ {ARCHITECTURE.md, GROWTH_PLAYBOOK.md, ENTERPRISE_GAP.md}
```

**Move, don't rewrite.** Keep `.git` histories via `git subtree` or `git filter-repo`. CI: `cargo check` (kernel) + `pytest` (business-os) + `next build` (factory) in parallel.

---

## 4. The unified flow — Idea → Live Business → 10× Loops

### 4.1 Genesis 2.0 — Idea in, business out (15 minutes)

```
User input: "fast fashion for Indian Gen-Z, thrifted aesthetics, weekly drops"
    │
    ▼
[1] extract_twin()           ─  LLM  ─▶ FounderTwin + 3-5 SALAAR questions
    │                                    (industry, stage, ARR, constraints, fears, forks)
[2] founder answers questions ─────────▶  refined Twin
    ▼
[3] generate_mission(twin)   ─  LLM  ─▶ Mission, North Star, target, deadline, priorities, decision_rules, 90-day objective
[4] generate_organization()  ─  LLM  ─▶ Divisions + Executives (role, mission, KPIs, L3 budget) + culture
[5] map_capabilities(twin,org) ─ det ─▶ capability checklist (email, CRM, invoicing, calendar, ecommerce, payments…)
[6] buildBusiness(idea, twin, mission, org)  ← NEW bridge
    ├── factory/blueprints: pick template or LLM-generate catalog (24 SKUs), brand, pricing (margin, AOV, valuationMultiple)
    ├── factory: scaffold Next.js store + Supabase orders + Razorpay checkout
    ├── kernel: provision org_id, vault, governance caps, audit stream
    └── business-os: init_system_model(org) → 16-function graph, schedule agents
    ▼
Live at:  https://drift-{org_id}.vercel.app  (or custom domain)
Admin at: /admin  (orders, revenue, AOV, valuation, agent board, approvals)
```

**The bridge (`business-os/factory_bridge.py` already exists — extend it):**
- `factory_bridge.build_storefront(org_id, blueprint) → {url, catalog, routes}` — today it scaffolds; after merge it also calls `blueprints/index.ts` LLM fallback and provisions Supabase `orders` table per org.
- Storefront is now **org-scoped, tenant-isolated** (org_id injected at deploy, checkout carries trace_id, audit logs in kernel).

### 4.2 10× Engine — how a static store becomes a compounding business

The store alone doesn't 10×. The **loops** do. SmartDecigen already has them — they just weren't wired to the store:

```
Revenue today ─┬─▶ Business OS signal scan (weekly): which of 16 functions is at-risk?
               │     └─▶ 12 agents decide (1 LLM call/turn, bounded prompt, deterministic)
               │           ├─ Growth Agent: "CAC up 20% → pause worst_channel, fund top_channel"
               │           ├─ Marketing Agent: "IG reels ROI > ads → 7-reel playbook → Notion page"
               │           ├─ Sales/Customer Agent: cart.abandoned → email/SMS via kernel invoke
               │           └─ Strategy Agent: "Adjacent market empty → blueprint for Drop 04"
               │
               ├─▶ Execution (kernel-gated): dispatcher → Composio tools → verification(read_back/webhook)
               │     └─▶ Audit trace → learning (cross-org anonymized via salaar)
               │
               ├─▶ Growth flywheel (new):
               │     Week 1-4:  agent-suggested experiments (7 reels + 50 micro-influencers + WhatsApp broadcast)
               │     Week 5-12: winning channel doubles spend (governance L3→L4 at ₹15K cap, then founder approves)
               │     Month 3+:  LTV loop: order.created → retention tasks → N-th drop → subscription/bundle
               │
               └─▶ Dashboard proves compounding: orders, revenue, AOV, repeat rate, valuation (2.5× fast fashion)
                   Weekly Review auto-memo + founder approval inbox (one-tap approve/edit/deny)
```

**10× math (explicit):** 10×/year = ~21% MoM. Achievable via: +10% orders (acquisition loop) + 5% AOV (bundle/upsell) + 5% repeat (retention) + 1% efficiency (ops). Each loop is an agent responsibility with a KPI, a decision prompt, and a verification step. No hand-waving.

**New monthly growth artifacts (to add):**
- `business-os/growth_engine.py` — experiment registry (hypothesis → tactic → spend → outcome → learning)
- `factory/src/components/GrowthBoard.tsx` — kanban: backlog → running → verify → learned
- `execution/handlers/razorpay.ts` + `execution/handlers/shopify.ts` (beyond Zoho) — revenue verification

---

## 5. Unified data model (shared ontology)

Add to `ontology/models.py` (SmartDecigen's single type system — no subsystem invents nouns):

```
Org { id, name, owner_user_id, north_star, target, deadline, priorities, decision_rules,
      system_model: {functions:16, version, scan_history[12]}, created_at }
Blueprint { id, org_id, idea, vertical, brand{name,tagline,colors}, pricing{range,avg,margin,valuationMultiple},
            catalog{count,categories,drops, products[]}, routes[], blueprint_version }
Storefront { id, org_id, blueprint_id, url, status, supabase_project, razorpay_key_ref(vault), last_deploy }
Agent { id, org_id, type, role, mission, kpis, schedule, authority(L1-L5), memory{decisions_made, actions_taken, learnings} }
Execution { id, trace_id, org_id, agent_type, capability, tool, args, reversibility, outcome, verification{method,status}, audit_ref }
Order { orderId, org_id, trace_id, at, name, phone, address, pincode, pay, items[], total, verified, rto_risk }
GrowthExperiment { id, org_id, hypothesis, tactic, channel, spend_inr, expected_outcome, actual_outcome, status, learning }
Approval { id, org_id, from_agent, summary, severity, status(pending/approved/denied), tool_calls[], estimated_cost_inr }
```

**DB separation (keep):** Postgres (kernel: governance, audit, secrets, idempotency), Mongo (business-os: orgs, agents, experiments, orders index), Supabase Postgres (factory: orders per org — RLS by org_id). All joined by `org_id` + `trace_id`.

---

## 6. API unification (one org_id, one auth)

| Surface | Today | Unified |
|---|---|---|
| Auth | Kernel JWT HMAC / Business-OS JWT / Factory none | **Kernel JWT for all** (`AuthConfig::from_env`, `AuthenticatedUser` extractor, `Authorization: Bearer`). Business-OS validates same token; Factory middleware checks it for `/admin` and `/api/checkout` |
| Secrets | Kernel vault per-org encrypted | **Vault is central**: Razorpay keys, Composio keys, Supabase keys all in `secrets` table (`load_org_cache()` + `resolve_placeholders()`) |
| Invoke | `POST /api/v1/invoke` (kernel) + `POST /api/agents/run` (business-os) | Keep both but business-os `execute_agent_decision()` calls kernel invoke internally (never bypasses governance) |
| Factory | None | `POST /factory/build {idea, answers?}` → returns blueprint + url; `POST /factory/iterate {org_id, instruction}` for LLM-regenerate catalog/brand |
| Growth | Scattered | `GET /api/v1/growth/board`, `POST /api/v1/growth/experiments`, `GET /api/v1/growth/weekly-review` |
| Checkout | `POST /api/checkout` (in-memory) | `POST /api/checkout` → writes Supabase (RLS) + emits `order.created` → agents; `GET /api/checkout` → RLS-scoped |

---

## 7. What to delete / deprecate

- `BusinessFactory/src/lib/factory.ts` 2-template stub → replaced by `factory/blueprints/*` + LLM fallback (keep signature `buildBusiness(idea)` for compat).
- In-memory `orders[]` in `factory/src/app/api/checkout/route.ts` → Supabase.
- Duplicate constitution forks — only `CONSTITUTION.md` at root.
- Any direct env interpolation for provider keys — must go through kernel vault.

---

## 8. Phased execution plan (realistic, parallelizable)

### Phase 0 — Freeze & repo surgery (2-3 days)
- [ ] Create `unified-platform` repo, import all three via `git subtree add`
- [ ] Move `ari/` → `kernel/`, `Smartdecision-main/backend` → `business-os/`, `BusinessFactory/` → `factory/`, `Smartdecision-main/frontend` → `frontend/`
- [ ] Promote `Smartdecision-main/CONSTITUTION.md` → `/CONSTITUTION.md` (frozen), delete `ari/docs/CONSTITUTION.md` dup
- [ ] Wire `docker-compose.yml` for local: `postgres:5432` (kernel), `mongo:27017` (business-os), `redis` (optional), `kernel:8080`, `business-os:8000`, `factory:3001`
- [ ] CI green: `cargo check`, `pytest -q`, `next build`

### Phase 1 — Unify auth & data (3-5 days)
- [ ] Kernel JWT becomes sole issuer: `business-os/security.py` validates kernel tokens; `factory/middleware.ts` gates `/admin` + `/api/checkout` with same token
- [ ] Centralize secrets: migrate Composio/Gmail/Slack/Stripe/Zoho/Razorpay keys into kernel vault; replace `${ENV}` reads with `resolve_placeholders()`
- [ ] Org provisioning: genesis creates `org_id` + kernel `org_governance` row (weekly spend bucket, L3 cap ₹15K) + audit stream
- [ ] Supabase per-org orders: `factory/src/lib/db.ts` (RLS on `org_id`), migrate `route.ts` from in-memory

### Phase 2 — Genesis 2.0 → live store (1-2 weeks)
- [ ] Harden `business-os/factory_bridge.py`: add `blueprints/` registry (fashion/beauty/food/digital/generic) + LLM fallback prompt for unknown ideas
- [ ] `factory/blueprints/index.ts`: `generateBlueprint(idea, twin, mission) → {brand, catalog[24], pricing, routes}` — one LLM call, validated against schema
- [ ] `POST /factory/build`: genesis twin→mission→org→blueprint→scaffold→deploy (Vercel or local `next start`), return `{url, blueprint, system_model}`
- [ ] E2E: `"streetwear for college students, ₹800-2500"` → live store in <5 min locally

### Phase 3 — Close the 10× loop (2-3 weeks)
- [ ] Wire storefront events → business-os: `order.created`, `cart.abandoned`, `checkout.started` (webhook → signal scan)
- [ ] Implement `growth_engine.py` + `GrowthBoard.tsx`: experiment backlog, weekly auto-suggestions per agent, spend enforcement via `kernel/governance.rs`
- [ ] Extend agents for commerce: `sales_agent` → abandoned cart email, `marketing_agent` → budget shifts, `growth_agent` → drop planning, `customer_agent` → retention
- [ ] Verification for revenue: Razorpay webhook → `verification.rs` `read_back`; order RTO model; weekly review memo
- [ ] Approval inbox surfaces spend >₹15K for founder one-tap

### Phase 4 — Harden & monetize (1-2 weeks)
- [ ] Payments: Razorpay (India) + Stripe fallback, Zoho invoicing, UPI QR
- [ ] Multi-tenant prod deploy: kernel on Fly/Koyeb, business-os on Render/Fly, factory on Vercel (all via existing `deploy/` configs)
- [ ] Billing: credit packs (`business-os/payments.py` + `TURN_COST=5`, `SIGNUP_CREDITS=100`), metering for LLM + tool calls
- [ ] Observability: OTEL (kernel) + `business-os/metrics.py` + factory analytics → unified audit log (trace_id)
- [ ] Security review: re-run ENTERPRISE_GAP 12 tests + `test_tenant_isolation`, `test_spend_cap`, `test_rate_limit`, `test_idempotency`

**Total: ~6-8 weeks to "idea → live business with autonomous growth" with a 2-person team.** Phase 2 alone is demoable for fundraising.

---

## 9. 10× playbook baked into product (not docs)

The platform ships with a default growth playbook per vertical (derived from `business_taxonomy.py` failures inverted):

1. **Day 0-7 — Launch:** 7 reels (hook: "₹1,799 steal / ₹11,999 fit") + 50 micro-influencers (gifting, 5-20k followers) + WhatsApp broadcast 500 contacts. Goal: first 20 orders. Agent: Marketing + Brand.
2. **Week 2-4 — Optimize:** kill channel with <3% conversion in 60 days (Decision Rule), double best channel. Abandoned cart email via kernel. Goal: CAC down 20%. Agent: Growth + Sales.
3. **Month 2 — Retain:** bundle ("3-pack"), repeat drop cadence (Monday 12PM), COD verification in 30 min to cut RTO. Goal: repeat rate 15%. Agent: Customer + Ops.
4. **Month 3+ — Expand:** adjacent drop (from opportunity scanner: `OPPORTUNITY_PATTERNS`), new blueprint variant in one click. Goal: MoM +21%. Agent: Strategy + Product.

Each step is an agent decision with a tool call gated by L3/L4, verified, and learned from.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Three languages, one platform → drift** | Keep boundaries (Rust kernel never rewrites in Python, Python never rewrites Rust). Contract is HTTP+JWT+trace_id+agent-spec.yaml |
| **LLM catalog hallucinates** | Schema-validated `blueprints/index.ts` + "NEW/LOW STOCK/BESTSELLER" rules + human edit in `/admin` before deploy |
| **Storefront RTO kills margin** | COD verification agent (call within 30 min), address/pincode validation, prepaid incentive — already in LAUNCH_KIT |
| **Agent spam / spend blowout** | Kernel `governance.rs` weekly spend bucket, L3→L4 escalation, idempotency, rate limit 60/s burst 100 |
| **Taxonomy not wired to agents** | Already partially: function health weights lens selection (`business_taxonomy.function_lens_map`) — extend to growth experiments |
| **Founder bottleneck (you are the bottleneck)** | Constitution principle 12 + Genesis `founder_bottleneck` field → agents auto-create tasks at L3 so founder approves instead of does |

---

## 11. What "done" looks like (verification)

- [ ] `cargo check` 0 errors (kernel), `pytest` green (business-os), `next build` green (factory)
- [ ] Typed idea `"sustainable sneakers, vulcanized, ₹2500"` → https://… live with 24 SKUs, checkout works, order appears in `/admin` + Supabase + kernel audit
- [ ] 12 agents run on schedule, daily Morning Brief posted, pending approvals in inbox, one experiment running
- [ ] Tenant isolation: `org_A` token cannot read `org_B` orders/agents/secrets (re-run `test_tenant_isolation`, `test_secrets_isolation`)
- [ ] Spend cap: exceeding weekly bucket → `ExecutionGate::Blocked` (re-run `test_spend_cap`)
- [ ] One growth experiment completes → verified outcome → learning stored → next week's suggestion improves

---

## 12. Names & positioning

- **Internal codename:** `FORGE`
- **External:** "SmartDecigen Forge — Idea → Business in minutes, 10× engine on autopilot"
- **Tagline:** "New drops weekly. Gone forever. Built by your Business OS."
- **Pricing wedge (from ari sales-agent):** $149–299/mo per org (ARPU that justifies LLM+tool costs; valuation 2.5× revenue for fast fashion DTC)

---

## 13. Immediate next commands (copy-paste)

```powershell
# 0) Create monorepo and import histories
mkdir unified-platform; cd unified-platform; git init
git subtree add --prefix=kernel "C:\Users\Dell -\Documents\Code\ari" main --squash
git subtree add --prefix=business-os "C:\Users\Dell -\Documents\Code\Smartdecision-main" main --squash
# factory is not yet a git repo — copy it
Copy-Item -Recurse "C:\Users\Dell -\Documents\Code\BusinessFactory" .\factory

# 1) Run each layer locally (existing commands still work)
cargo check --manifest-path kernel\runtime\src\host\Cargo.toml
cargo check --manifest-path kernel\cli\Cargo.toml
pip install -r business-os\requirements.txt; pytest business-os\tests -q
npm --prefix factory install; npm --prefix factory run build
```

This file is the plan. No extra doc needed — start at Phase 0.
