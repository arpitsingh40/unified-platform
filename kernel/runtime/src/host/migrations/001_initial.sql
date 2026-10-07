-- ARI initial schema — enterprise audit-grade, idempotent

-- governance key/value (global kill_switch, dry_run, etc.)
CREATE TABLE IF NOT EXISTS governance_state (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- per-org governance overrides
CREATE TABLE IF NOT EXISTS org_governance (
    org_id TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- weekly spend bucket per org
CREATE TABLE IF NOT EXISTS org_spend (
    org_id TEXT NOT NULL,
    week_start TEXT NOT NULL,
    total DOUBLE PRECISION NOT NULL DEFAULT 0,
    PRIMARY KEY (org_id, week_start)
);

-- approvals
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    modifications JSONB
);
CREATE INDEX IF NOT EXISTS idx_approvals_org ON approvals(org_id, status);

-- agent memory (versioned, TTL, tags)
CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value BYTEA NOT NULL,
    expires_at TIMESTAMPTZ,
    version BIGINT NOT NULL DEFAULT 1,
    tags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, key)
);
CREATE INDEX IF NOT EXISTS idx_agent_memory_expires ON agent_memory(expires_at) WHERE expires_at IS NOT NULL;

-- invocation audit (append-only, never updated)
CREATE TABLE IF NOT EXISTS invocations (
    invocation_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    trace_parent TEXT,
    success BOOLEAN NOT NULL,
    total_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_time_ms BIGINT NOT NULL DEFAULT 0,
    decision JSONB,
    executions JSONB NOT NULL DEFAULT '[]'::jsonb,
    verification JSONB NOT NULL DEFAULT '[]'::jsonb,
    error TEXT,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invocations_org ON invocations(org_id, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_invocations_agent ON invocations(agent_id, completed_at DESC);

-- audit log: every sensitive action (auth, governance change, approval resolve, spend)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    org_id TEXT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT,
    trace_id TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_log_org_ts ON audit_log(org_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_trace ON audit_log(trace_id) WHERE trace_id IS NOT NULL;

-- secrets vault (encrypted at rest via memory encryption key)
CREATE TABLE IF NOT EXISTS secrets (
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,
    encrypted_value BYTEA NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, name)
);
