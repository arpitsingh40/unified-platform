//! Idempotency: `Idempotency-Key` header dedup (24h) per org.
//! Backed by `idempotency_keys` table; falls back to in-memory if DB unavailable.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

pub struct IdempotencyStore {
    pool: Option<sqlx::PgPool>,
    mem: Arc<RwLock<HashMap<String, serde_json::Value>>>, // key: "org:key" → result
}

impl IdempotencyStore {
    pub fn new(pool: Option<sqlx::PgPool>) -> Self {
        Self { pool, mem: Arc::new(RwLock::new(HashMap::new())) }
    }

    fn cache_key(org_id: &str, key: &str) -> String { format!("{}:{}", org_id, key) }

    pub async fn get(&self, org_id: &str, key: &str) -> Result<Option<serde_json::Value>> {
        if let Some(pool) = &self.pool {
            let row: Option<(serde_json::Value,)> = sqlx::query_as(
                "SELECT result FROM idempotency_keys WHERE org_id=$1 AND key=$2 AND expires_at > NOW()"
            )
            .bind(org_id).bind(key).fetch_optional(pool).await?;
            if let Some((v,)) = row { return Ok(Some(v)); }
        }
        Ok(self.mem.read().await.get(&Self::cache_key(org_id, key)).cloned())
    }

    pub async fn put(&self, org_id: &str, key: &str, invocation_id: &str, result: &serde_json::Value) -> Result<()> {
        if let Some(pool) = &self.pool {
            let _ = sqlx::query(
                "INSERT INTO idempotency_keys (org_id, key, invocation_id, result) VALUES ($1,$2,$3,$4) ON CONFLICT (org_id, key) DO NOTHING"
            )
            .bind(org_id).bind(key).bind(invocation_id).bind(result)
            .execute(pool).await;
        }
        self.mem.write().await.insert(Self::cache_key(org_id, key), result.clone());
        Ok(())
    }

    pub async fn cleanup_expired(&self) -> Result<u64> {
        if let Some(pool) = &self.pool {
            let r = sqlx::query("DELETE FROM idempotency_keys WHERE expires_at < NOW()").execute(pool).await?;
            return Ok(r.rows_affected());
        }
        Ok(0)
    }
}
