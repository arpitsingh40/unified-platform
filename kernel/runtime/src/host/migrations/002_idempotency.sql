-- Idempotency dedup: cache invocation result per (org_id, idempotency_key) for 24h
CREATE TABLE IF NOT EXISTS idempotency_keys (
    org_id TEXT NOT NULL,
    key TEXT NOT NULL,
    invocation_id TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    PRIMARY KEY (org_id, key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_keys(expires_at);
