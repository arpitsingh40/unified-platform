# sales-agent — L3 pipeline health wedge

**One outcome:** no stalled deal >14 days without action. **Price:** $149/mo per org (L3). Land 10 design partners → 100 → $150k MRR → expand to `finance-agent`, `ops-agent`.

## Quick demo (no DB, no server)

```bash
cargo run --example demo -p sales-agent
```

Expected:

```
STALLED — FOLLOW_UP + 2 tool_calls (crm.read auto, email.send approval-gated)
HEALTHY — NOTHING
EMPTY   — NOTHING
```

## Build WASM

```bash
cargo build -p sales-agent --target wasm32-wasip1          # debug 2.1 MB
cargo build -p sales-agent --target wasm32-wasip1 --release # release (opt-level s + LTO)
cargo test -p sales-agent
```

## Full host loop (needs Postgres)

```
DATABASE_URL=postgresql://user:pass@localhost:5432/ari \
ARI_JWT_SECRET=$(openssl rand -hex 32) \
cargo run -p ari-runtime-host
```

Then invoke via `POST /api/v1/invoke` with `Authorization: Bearer <jwt>` + `Idempotency-Key`. See `DEMO.md` for the exact curl.

## What this proves (enterprise)

- `capabilities` + `governance.requires_approval` + `template_required` — `email.send` queued as pending_approval under L3.
- `verification` — `email.send → webhook`, `crm.write → read_back`, `document.generate → human_review` mapped in `agent.yaml`.
- `metrics` — `verification_success_rate` per org (the funding demo).
- `tenancy` — `org_A` cannot see `org_B` deals (`assert_tenant` → 403).
- `audit_log` — every invocation + governance decision has `trace_id`.
- `idempotency` — same `Idempotency-Key` returns cached result (24h), no double-spend.

## Files

- `Cargo.toml` — ndylib + rlib, host links as `sales-agent` crate
- `src/lib.rs` — `decide()` + `is_stalled(14d)`, `run` WASI export, `#[cfg(test)]`
- `agent.yaml` — enterprise contract (caps, governance, verification, decision_schema)
- `examples/demo.rs` — offline 3-scenario harness (no infra)
- `DEMO.md` — full curl walkthrough + screenshot checklist

## Spec (ship contract)

`spec/agent-spec.yaml` is the canonical contract: capabilities, authority L3, `limits.max_cost_usd_per_invocation: 0.50`, decision_schema, verification table, learning retention 365d. This example's `agent.yaml` is a trimmed deployable subset of that spec.
