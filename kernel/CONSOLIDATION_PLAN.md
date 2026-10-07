# Consolidation Plan — One Repo, One Constitution

> **Principle:** `ARI = kernel`, `SmartDecigen = Business OS`, `sales-agent = vertical`. One `CONSTITUTION.md` is the source of truth.

## Repository shape (target)

```
ari/
  runtime/src/host/          ← kernel (WASM + governance + memory + identity + audit + secrets)
    src/{auth,tenancy,audit,secrets,idempotency,governance,memory,capabilities,verification,approval,identity,runtime,metrics}.rs
    migrations/{001_initial,002_idempotency}.sql
  cli/                       ← `ari build/push/deploy/run` (already compiles)
  sdk/{python,typescript}/   ← thin clients (add Authorization: Bearer header)
  spec/agent-spec.yaml       ← single agent contract (capabilities + governance + decision_schema)
  runtime/src/host/wit/ari.wit ← component model world (frozen)
  examples/sales-agent/      ← reference vertical (see below)
  docs/CONSTITUTION.md       ← copied from smartdecision (12 principles, frozen)
  ENTERPRISE_GAP.md
  CONSOLIDATION_PLAN.md (this file)
```

## Relation to SmartDecigen (do NOT duplicate)

- **Import once:** `smartdecision/docs/CONSTITUTION.md` → `ari/docs/CONSTITUTION.md` (verbatim, ratified July 2026). No fork.
- **Reuse, don't rewrite:**
  - `smartdecision/backend/governance.py:execution_gate` → `ari/runtime/src/host/src/governance.rs:check_execution` (done — weekly spend bucket, kill switch, dry-run).
  - `smartdecision/backend/business_os.py` lifecycle → ARI `AgentRuntime::background_tasks` scheduler (next: cron-based `schedule` field from `agent-spec.yaml`).
  - `smartdecision/backend/executive.py` Executive DNA → ARI `AgentMetadata + AgentIdentity` (authority L1-L5, decision_rights, spending_limit).
  - `smartdecision/backend/ontology/*` → keep as reference; ARI uses `spec/agent-spec.yaml` as the runtime ontology snapshot.
  - `smartdecision/backend/capabilities.py` → already mirrored in `capabilities.rs` (Composio, MCP, HTTP providers).

- **Keep SmartDecigen running** as the Business OS control plane (FastAPI + React). ARI host is the trusted executor underneath. SmartDecigen calls `POST /api/v1/invoke` with `AuthenticatedUser.org_id`.

## Migration steps — shipped

1. ✅ **Docs import** — `docs/CONSTITUTION.md` copied verbatim, frozen; `ari.wit` + `agent-spec.yaml` frozen as v1.
2. ✅ **Auth wired** — `lib.rs:start_rich_control_server` + `runtime.rs:start_control_server` both enforce `AuthenticatedUser` + `assert_tenant`; `Extension(AuthState)`, `/health`/`/metrics` public, rest requires Bearer.
3. ✅ **Vault integrated** — `SecretsManager::load_org_cache()` per invocation, `resolve_placeholders()` replaces env interpolation.
4. ✅ **Example vertical** — `examples/sales-agent/agent.yaml` + `README.md` runnable wedge ($149/mo wedge).
5. ✅ **Verification webhook** — `POST /webhooks/verify/:trace_id` + `POST /webhooks/approval/:approval_id` with HMAC-SHA256 (constant-time), backed by `VerificationEngine`.
6. ✅ **OTEL + idempotency** — `telemetry::maybe_init_otel` (feature `otel`), `idempotency.rs:IdempotencyStore` + `002_idempotency.sql`, `Idempotency-Key` dedup on `POST /api/v1/invoke`, `governor 0.6` rate layer (60/s burst 100).

## What NOT to do

- Do not merge SmartDecigen's Python backend into Rust. Keep language boundary.
- Do not rewrite ARI in Python. Keep WASM boundary.
- Do not add new WIT methods until a vertical needs them.

## Sales-agent vertical (the wedge)

`spec/agent-spec.yaml` already defines `sales-agent` (pipeline health, stalled >14d, proposal drafting, `requires_approval`, `template_required`). The example under `examples/sales-agent/` makes it runnable and monetizable at $99-299/mo per org — the $1T wedge.

- **Approval gate:** `crm.write`, `email.send`, `document.generate` require approval (L3 → L4). `crm.read`, `web.search` are L3 auto.
- **Verification:** `email.send` → webhook (delivery), `crm.write` → read_back, `document.generate` → human_review.
- **Metric that matters:** `verification_success_rate` + `total_cost_usd` per org — the demo to raise capital.
