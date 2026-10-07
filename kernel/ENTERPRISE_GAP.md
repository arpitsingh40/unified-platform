# ARI Enterprise Gap — Closed

Kernel v0.2: `host` + `cli` compile clean, `cargo build` green (both binaries). All 12 enterprise blockers against the CONSTITUTION.md (12 principles) are now closed.

| # | Gap | Fix | Status |
|---|-----|-----|--------|
| 1 | **Secrets via `${ENV}` interpolation** | `secrets.rs` per-org vault (AES-GCM random nonce, `secrets` table), `load_org_cache()` + `resolve_placeholders()`. Provider auth resolves from vault, not env. | ✅ |
| 2 | **No auth / org scoping on API** | `auth.rs` JWT HS256 + Axum `AuthenticatedUser` extractor (Bearer, issuer/audience, exp). `AuthConfig::from_env()` for zero-config dev. | ✅ |
| 3 | **Cross-tenant access possible** | `tenancy.rs` `assert_tenant` / `assert_capability_tenant` — every handler checks `auth.org_id == resource.org_id`. | ✅ |
| 4 | **Governance persistence was `Ok(())` stubs** | `governance.rs` now hits `governance_state`, `org_governance`, `org_spend` (weekly Monday bucket), `approvals` with real upserts. `record_spend()` + `check_execution()` use DB as authoritative. | ✅ |
| 5 | **Hardcoded AES nonce (`unique_nonce_12`)** | `memory.rs` + `secrets.rs` generate random 12-byte nonce per encrypt, prepend to ciphertext. | ✅ |
| 6 | **No audit trail** | `audit.rs` append-only `audit_log` (actor/action/resource/trace_id/details JSONB), `new_trace_id()` + W3C `trace_parent_header()`. | ✅ |
| 7 | **Build blocked (79 errors)** | Fixed: wasmtime component import, figment/redis/wit-bindgen features, sqlx offline (dynamic queries), approval modifications clone, metrics 0.21 API, rcgen 0.11, telemetry OnceLock, AgentInstance non-Serialize split. | ✅ |
| 8 | **No migrations** | `migrations/001_initial.sql` idempotent + `002_idempotency.sql` (`idempotency_keys` 24h). | ✅ |
| 9 | **No Axum auth middleware wired** | `lib.rs:start_rich_control_server` — `Extension(AuthState)` + `AuthenticatedUser` on every route; `/health` + `/metrics` public, rest requires Bearer + tenant filter. `runtime.rs:start_control_server` also enforces `AuthenticatedUser` + tenant filter. | ✅ |
| 10 | **Verification webhook server missing** | `verification.rs:verify_webhook_signature()` HMAC-SHA256 constant-time (subtle), `VerificationEngine::handle_webhook_callback` + `handle_approval_callback`. Routes `POST /webhooks/verify/:trace_id` + `POST /webhooks/approval/:approval_id` (HMAC via `ARI_WEBHOOK_SECRET`, also in rich server). | ✅ |
| 11 | **OTEL exporter not wired** | `telemetry.rs:maybe_init_otel(endpoint)` — no-op cold, wired to `lib.rs` via `config.telemetry.otel_endpoint`; with `--features otel` it builds an OTLP Tonic exporter (service.name `ari-runtime-host`). Without the feature it logs and stays local. `Cargo.toml` feature `otel = [opentelemetry, opentelemetry-otlp, tracing-opentelemetry]`. | ✅ |
| 12 | **No rate limiting / idempotency guard** | `lib.rs` rate layer `governor 0.6` (60 req/s burst 100, returns 429), `idempotency.rs:IdempotencyStore` (`idempotency_keys` table + in-memory fallback), `invoke_rich` checks `Idempotency-Key` header: cached hit returns prior result, miss stores `invocation_id → result` for 24h. `AriRuntime` now owns `idempotency: Arc<IdempotencyStore>`. | ✅ |

## Verify

```bash
cargo check   # 0 errors (warnings only, host + cli)
cargo build   # Finished dev — host 1m13s, cli 1m52s
```

- `test_tenant_isolation` — `org_A` token cannot invoke agent in `org_B` (403)
- `test_secrets_isolation` — `org_A` secret not visible to `org_B` even via `${NAME}`
- `test_spend_cap` — exceed weekly cap → `ExecutionGate::Blocked`
- `test_audit_append` — invocation creates `audit_log` row with `trace_id`
- `test_jwt_expiry` — expired token → 401
- `test_idempotency` — same `Idempotency-Key` returns cached result, no double invoke
- `test_rate_limit` — 100th burst request within 1s window → 429
