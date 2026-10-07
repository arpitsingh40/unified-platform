//! Append-only audit log + trace propagation.

use anyhow::Result;
use serde_json::Value as JsonValue;

#[derive(Debug, Clone)]
pub struct AuditEvent {
    pub org_id: Option<String>,
    pub actor: String,
    pub action: String,
    pub resource: Option<String>,
    pub trace_id: Option<String>,
    pub details: JsonValue,
}

pub struct AuditLog {
    pool: sqlx::PgPool,
}

impl AuditLog {
    pub fn new(pool: sqlx::PgPool) -> Self { Self { pool } }

    pub async fn record(&self, e: AuditEvent) -> Result<()> {
        sqlx::query("INSERT INTO audit_log (org_id, actor, action, resource, trace_id, details) VALUES ($1,$2,$3,$4,$5,$6)")
            .bind(&e.org_id).bind(&e.actor).bind(&e.action).bind(&e.resource).bind(&e.trace_id).bind(&e.details)
            .execute(&self.pool).await?;
        tracing::info!(action=%e.action, actor=%e.actor, trace_id=?e.trace_id, org_id=?e.org_id, "audit");
        Ok(())
    }

    pub async fn list(&self, org_id:&str, limit:i64) -> Result<Vec<AuditRow>> {
        let rows: Vec<(uuid::Uuid, chrono::DateTime<chrono::Utc>, Option<String>, String, String, Option<String>, Option<String>, JsonValue)> =
            sqlx::query_as("SELECT id, ts, org_id, actor, action, resource, trace_id, details FROM audit_log WHERE org_id=$1 ORDER BY ts DESC LIMIT $2")
            .bind(org_id).bind(limit).fetch_all(&self.pool).await.unwrap_or_default();
        Ok(rows.into_iter().map(|(id, ts, org_id, actor, action, resource, trace_id, details)| AuditRow{ id, ts, org_id, actor, action, resource, trace_id, details }).collect())
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct AuditRow {
    pub id: uuid::Uuid,
    pub ts: chrono::DateTime<chrono::Utc>,
    pub org_id: Option<String>,
    pub actor: String,
    pub action: String,
    pub resource: Option<String>,
    pub trace_id: Option<String>,
    pub details: JsonValue,
}

pub fn new_trace_id() -> String { uuid::Uuid::new_v4().to_string() }
pub fn trace_parent_header(trace_id: &str) -> String {
    let hex = trace_id.replace('-', "");
    let padded = format!("{:0<32}", &hex[..hex.len().min(32)]);
    let parent = &uuid::Uuid::new_v4().to_string().replace('-', "")[..16];
    format!("00-{}-{}-01", padded, parent)
}
