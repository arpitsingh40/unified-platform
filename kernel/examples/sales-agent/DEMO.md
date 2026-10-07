# Demo — sales-agent wedge

No DB required for local demo. Host falls back to `sales_agent::decide` (pure) + simulated capability registry; governed flow is identical.

## Option A — offline decision (no build, no server)

```bash
cargo run --example demo -p sales-agent
```

Output:

```
STALLED — FOLLOW_UP + 2 tool_calls (crm.read auto, email.send approval-gated)
HEALTHY — NOTHING
EMPTY   — NOTHING
```

## Option B — full host loop (governance → invoke → verification → audit)

With Postgres running (migrations auto-apply via `lib.rs`):

```bash
# 1. Start host (DATABASE_URL must point to a reachable DB; without it host will error at startup — that is expected)
DATABASE_URL=postgresql://user:pass@localhost:5432/ari \
ARI_JWT_SECRET=$(openssl rand -hex 32) \
ARI_TELEMETRY__LOG_JSON=false \
cargo run -p ari-runtime-host

# 2. In another shell, load the agent
curl -H "Authorization: Bearer $(cargo run -p ari-runtime-host --bin gen-jwt 2>/dev/null)" \
  -X POST http://localhost:8080/api/v1/agents/load -d '{"agent_id":"sales-agent","component":"./examples/sales-agent/target/wasm32-wasip1/debug/sales_agent.wasm"}'

# 3. Invoke with stalled pipeline (approval-gated second tool)
curl -H "Authorization: Bearer $JWT" -H "Idempotency-Key: $(uuidgen)" \
  http://localhost:8080/api/v1/invoke -d '{
    "invocation_id": "inv_001",
    "agent_id": "sales-agent",
    "org_id": "org_demo",
    "context": {
      "pipeline": [
        {"id":"opp_1","name":"Acme — Expansion","stage":"Negotiation","amount":45000,"owner":"alice@co.com","last_activity_at":"2026-09-18T00:00:00Z"},
        {"id":"opp_2","name":"Globex — Pilot","stage":"Proposal","amount":12000,"owner":"bob@co.com","last_activity_at":"2026-10-05T00:00:00Z"}
      ]
    }
  }'

# Expect: decision.action=FOLLOW_UP, executions[0]=crm.read success, executions[1]=email.send pending_approval or executed depending on governance config,
#         verification records, audit_log entry with trace_id.
```

## What to screenshot for the $149/mo pitch

1. `FOLLOW_UP` reasoning: "1 stalled deals detected (>14d). Highest value: Acme — Expansion ($45000)"
2. Governance gate: `email.send` requires_approval → `pending_approval` (demo of L3 vs L4).
3. Verification: `email.send → webhook (delivery)`, `crm.write → read_back`.
4. Audit trail: `audit_log` has row with `trace_id`.
5. Idempotency: resend same `Idempotency-Key` → identical response, no double-spend.
6. Tenancy: `org_A` token cannot GET `org_B` agents → 403.

## Build WASM

```bash
cargo build -p sales-agent --target wasm32-wasip1          # debug 2.1 MB
cargo build -p sales-agent --target wasm32-wasip1 --release # small + LTO
```

## Files

- `Cargo.toml` — ndylib + rlib, `opt-level s` release
- `src/lib.rs` — `decide()` + `is_stalled()`, `#[no_mangle] run` export
- `agent.yaml` — enterprise contract (caps, governance, verification, decision_schema)
- `examples/demo.rs` — 3-scenario offline demo (no infra)
