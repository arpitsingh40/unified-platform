# FORGE — Idea → Business → 10×/year

> **One idea in. Entire business out. Then autonomous growth loops compound to 10× YoY.**

Single constitution. Three layers. One \org_id\.

\\\
kernel/        ← ARI (Rust/WASM)      — auth, vault, governance, audit, verification, rate limit
business-os/   ← SmartDecigen (Python) — genesis, 16-function graph, 12 agents, execution (1403 tools)
factory/       ← BusinessFactory (Next.js) — blueprints → live storefront (Supabase + Razorpay)
frontend/      ← control plane UI
CONSTITUTION.md — 12 principles (frozen)
\\\

## Quickstart (local, 5 min)
\\\powershell
# 1) infra
docker compose up -d   # postgres (kernel) + mongo (business-os)

# 2) kernel (Rust)
cargo check --manifest-path kernel\runtime\src\host\Cargo.toml

# 3) business-os (Python)
pip install -r business-os\requirements.txt
pytest business-os\tests -q

# 4) factory (Next.js)
npm --prefix factory install
npm --prefix factory run dev   # http://localhost:3001
\\\

## Docs
- \CONSTITUTION.md\ — 12 principles (source of truth)
- \docs/UNIFIED_PLATFORM_PLAN.md\ — full merge plan (architecture, data model, phased execution)
- \kernel/ENTERPRISE_GAP.md\ — 12 enterprise gaps (closed)
- \kernel/CONSOLIDATION_PLAN.md\ — ARI repo shape

## Phases
- P0 repo surgery + CI green
- P1 unified JWT + vault + Supabase RLS orders
- P2 Genesis 2.0 → \POST /factory/build {idea}\ → live store
- P3 growth loops (GrowthBoard + experiments + verification)
- P4 payments, deploy, billing, OTEL
