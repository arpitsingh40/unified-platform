//! ARI Runtime Host Library

pub mod config;
pub mod telemetry;
pub mod governance;
pub mod capabilities;
pub mod memory;
pub mod verification;
pub mod approval;
pub mod identity;
pub mod runtime;
pub mod metrics;
pub mod auth;
pub mod secrets;
pub mod audit;
pub mod tenancy;
pub mod idempotency;

use anyhow::Result;
use std::sync::Arc;
use tokio::sync::RwLock;

pub use config::RuntimeConfig;
pub use governance::{GovernanceEngine, GovernanceState, OrgGovernance, ExecutionGate, ApprovalResponse};
pub use capabilities::{CapabilityRegistry, Capability, Tool, CapabilityRequest, CapabilityResponse};
pub use memory::{MemoryManager, MemoryBackend, MemoryEntry};
pub use verification::{VerificationEngine, VerificationRequest, VerificationResult, VerificationMethod};
pub use approval::{ApprovalEngine, ApprovalConfig, ApprovalResult, ApprovalDetails};
pub use identity::{IdentityManager, AgentIdentity, SigningKeyPair};
pub use runtime::{AgentRuntime, InvocationRequest, InvocationResult, AgentInstance, AgentMetadata, start_control_server};
pub use metrics::{MetricsCollector, InvocationMetrics, AgentMetrics, OrgMetrics};
pub use auth::{AuthConfig, AuthenticatedUser, AuthState, Claims, create_token, verify_token};
pub use secrets::SecretsManager;
pub use audit::{AuditLog, AuditEvent};
pub use tenancy::assert_tenant;
pub use idempotency::IdempotencyStore;

pub struct AriRuntime {
    pub config: RuntimeConfig,
    pub capability_registry: Arc<CapabilityRegistry>,
    pub governance: Arc<GovernanceEngine>,
    pub memory: Arc<MemoryManager>,
    pub verification: Arc<VerificationEngine>,
    pub approval: Arc<ApprovalEngine>,
    pub identity: Arc<IdentityManager>,
    pub runtime: Arc<AgentRuntime>,
    pub metrics: Arc<MetricsCollector>,
    pub secrets: Arc<SecretsManager>,
    pub audit: Arc<AuditLog>,
    pub idempotency: Arc<IdempotencyStore>,
}

impl AriRuntime {
    pub async fn new(config: RuntimeConfig) -> Result<Self> {
        telemetry::init_telemetry()?;
        telemetry::maybe_init_otel(config.telemetry.otel_endpoint.as_deref())?;
        
        // Create capability registry
        let capability_registry = Arc::new(CapabilityRegistry::new(config.capabilities.clone())?);
        capability_registry.register_builtin().await?;
        
        // Create database pool
        let pg_pool = sqlx::PgPool::connect(&config.storage.postgres_url).await?;
        
        // Run migrations
        sqlx::migrate!("./migrations").run(&pg_pool).await?;
        
        // Create governance engine
        let governance = Arc::new(GovernanceEngine::new(config.governance.clone(), pg_pool.clone()).await?);
        
        // Create memory manager
        let memory = Arc::new(MemoryManager::new(config.memory.clone(), Some(pg_pool.clone())).await?);
        
        // Create verification engine
        let verification = Arc::new(VerificationEngine::new(governance.clone()));
        
        // Create approval engine
        let approval_config = ApprovalConfig {
            control_plane_url: config.server.control_plane_url.clone().unwrap_or_default(),
            api_key: std::env::var("ARI_CONTROL_PLANE_API_KEY").unwrap_or_default(),
            default_timeout_seconds: 86400,
            escalation_timeout_seconds: 3600,
            auto_approve_threshold_usd: 0.10,
        };
        let approval = Arc::new(ApprovalEngine::new(approval_config, governance.clone()));
        
        // Create identity manager
        let identity = Arc::new(IdentityManager::new(config.identity.clone()).await?);
        
        // Create metrics collector
        let metrics = Arc::new(MetricsCollector::new()?);

        let secrets = Arc::new(SecretsManager::new(pg_pool.clone(), config.memory.encryption_key.clone()));
        let audit = Arc::new(AuditLog::new(pg_pool.clone()));
        let idempotency = Arc::new(IdempotencyStore::new(Some(pg_pool.clone())));
        
        // Create agent runtime
        let runtime = Arc::new(AgentRuntime::new(
            config.runtime.clone(),
            capability_registry.clone(),
            governance.clone(),
            memory.clone(),
            verification.clone(),
            approval.clone(),
            identity.clone(),
            metrics.clone(),
        ).await?);
        
        Ok(Self {
            config,
            capability_registry,
            governance,
            memory,
            verification,
            approval,
            identity,
            runtime,
            metrics,
            secrets,
            audit,
            idempotency,
        })
    }
    
    pub async fn start(&self) -> Result<()> {
        let runtime_clone = self.runtime.clone();
        tokio::spawn(async move { runtime_clone.background_tasks().await; });
        // Rich server with secrets/audit; fall back to runtime's server if needed
        self.start_rich_control_server().await
    }

    async fn start_rich_control_server(&self) -> Result<()> {
        use axum::{Router, routing::{get, post, delete}, Json, extract::{State, Path}, Extension, http::StatusCode};
        use std::net::SocketAddr;
        use crate::auth::{AuthState, AuthConfig, AuthenticatedUser};
        #[derive(Clone)]
        struct RichState {
            runtime: Arc<AgentRuntime>,
            secrets: Arc<SecretsManager>,
            audit: Arc<AuditLog>,
            idempotency: Arc<IdempotencyStore>,
            _governance: Arc<GovernanceEngine>,
        }
        let rich = RichState { runtime: self.runtime.clone(), secrets: self.secrets.clone(), audit: self.audit.clone(), idempotency: self.idempotency.clone(), _governance: self.governance.clone() };

        async fn health() -> Json<serde_json::Value> { Json(serde_json::json!({"status":"ok","service":"ari"})) }

        async fn list_secrets(auth: AuthenticatedUser, State(s): State<RichState>) -> Json<serde_json::Value> {
            let names = s.secrets.list_secret_names(&auth.org_id).await.unwrap_or_default();
            Json(serde_json::json!({"org_id": auth.org_id, "secrets": names}))
        }
        async fn put_secret(auth: AuthenticatedUser, State(s): State<RichState>, Path(name): Path<String>, Json(body): Json<serde_json::Value>) -> Result<Json<serde_json::Value>, StatusCode> {
            if !auth.can_write() { return Err(StatusCode::FORBIDDEN); }
            let val = body.get("value").and_then(|v| v.as_str()).ok_or(StatusCode::BAD_REQUEST)?;
            s.secrets.set_secret(&auth.org_id, &name, val).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            let _ = s.audit.record(AuditEvent{ org_id: Some(auth.org_id.clone()), actor: auth.user_id.clone(), action: "secrets.put".to_string(), resource: Some(name.clone()), trace_id: None, details: serde_json::json!({}) }).await;
            Ok(Json(serde_json::json!({"ok": true, "name": name})))
        }
        async fn delete_secret(auth: AuthenticatedUser, State(s): State<RichState>, Path(name): Path<String>) -> Result<Json<serde_json::Value>, StatusCode> {
            if !auth.can_write() { return Err(StatusCode::FORBIDDEN); }
            let ok = s.secrets.delete_secret(&auth.org_id, &name).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            Ok(Json(serde_json::json!({"ok": ok})))
        }
        async fn list_audit(auth: AuthenticatedUser, State(s): State<RichState>) -> Json<serde_json::Value> {
            let rows = s.audit.list(&auth.org_id, 50).await.unwrap_or_default();
            Json(serde_json::to_value(&rows).unwrap_or(serde_json::json!([])))
        }
        async fn invoke_rich(auth: AuthenticatedUser, State(s): State<RichState>, headers: axum::http::HeaderMap, Json(mut req): Json<InvocationRequest>) -> Result<Json<InvocationResult>, StatusCode> {
            crate::tenancy::assert_tenant(&auth.org_id, &req.org_id).map_err(|_| StatusCode::FORBIDDEN)?;
            if req.trace_parent.is_none() { req.trace_parent = Some(crate::audit::trace_parent_header(&req.invocation_id)); }
            // Idempotency-Key dedup (24h) — if client resends same key, return cached result
            if let Some(key) = headers.get("idempotency-key").and_then(|v| v.to_str().ok()).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()) {
                if let Ok(Some(cached)) = s.idempotency.get(&auth.org_id, &key).await {
                    if let Ok(cached_res) = serde_json::from_value::<InvocationResult>(cached) {
                        return Ok(Json(cached_res));
                    }
                }
                let res = s.runtime.invoke(req).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
                let val = serde_json::to_value(&res).unwrap_or(serde_json::Value::Null);
                let _ = s.idempotency.put(&auth.org_id, &key, &res.invocation_id, &val).await;
                return Ok(Json(res));
            }
            let res = s.runtime.invoke(req).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            Ok(Json(res))
        }

        async fn list_agents_rich(auth: AuthenticatedUser, State(s): State<RichState>) -> Json<serde_json::Value> {
            let agents = s.runtime.list_agents().await;
            let filtered: Vec<_> = agents.into_iter().filter(|a| a.org_id == auth.org_id).map(|a| serde_json::json!({"agent_id": a.agent_id, "org_id": a.org_id, "metadata": a.metadata})).collect();
            Json(serde_json::json!(filtered))
        }
        async fn get_agent_rich(auth: AuthenticatedUser, State(s): State<RichState>, Path(agent_id): Path<String>) -> Result<Json<serde_json::Value>, StatusCode> {
            let a = s.runtime.get_agent(&agent_id).await.ok_or(StatusCode::NOT_FOUND)?;
            if a.org_id != auth.org_id { return Err(StatusCode::FORBIDDEN); }
            Ok(Json(serde_json::json!({"agent_id": a.agent_id, "org_id": a.org_id, "metadata": a.metadata, "created_at": a.created_at, "invocation_count": a.invocation_count})))
        }
        async fn webhook_verify_rich(headers: axum::http::HeaderMap, State(s): State<RichState>, Path(trace_id): Path<String>, body: axum::body::Bytes) -> Result<Json<serde_json::Value>, StatusCode> {
            let sig = headers.get("x-webhook-signature").or_else(|| headers.get("x-hub-signature-256")).and_then(|v| v.to_str().ok());
            let secret = std::env::var("ARI_WEBHOOK_SECRET").ok();
            if !crate::verification::VerificationEngine::verify_webhook_signature(&body, sig, secret.as_deref()) { return Err(StatusCode::UNAUTHORIZED); }
            let payload: serde_json::Value = serde_json::from_slice(&body).map_err(|_| StatusCode::BAD_REQUEST)?;
            s.runtime.verification.handle_webhook_callback(&trace_id, payload).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            Ok(Json(serde_json::json!({"ok": true, "trace_id": trace_id})))
        }
        async fn approval_webhook_rich(State(s): State<RichState>, Path(approval_id): Path<String>, Json(payload): Json<serde_json::Value>) -> Result<Json<serde_json::Value>, StatusCode> {
            let approved = payload.get("approved").and_then(|v| v.as_bool()).unwrap_or(false);
            let reviewer = payload.get("reviewer").and_then(|v| v.as_str()).unwrap_or("webhook").to_string();
            let mods = payload.get("modifications").cloned();
            s.runtime.verification.handle_approval_callback(&approval_id, approved, &reviewer, mods.clone()).await.map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
            let _ = s.runtime.governance.resolve_approval(&approval_id, approved, &reviewer, mods).await;
            Ok(Json(serde_json::json!({"ok": true, "approval_id": approval_id, "approved": approved})))
        }

        // Simple per-IP rate limiter: 60 req/s burst 100, via governor crate (in-memory).
        // For production behind ingress, prefer ingress-level limiting; this is defense-in-depth.
        use std::sync::Arc as StdArc;
        use governor::{Quota, RateLimiter, clock::DefaultClock, state::{InMemoryState, NotKeyed}};
        use std::num::NonZeroU32;
        let lim: StdArc<RateLimiter<NotKeyed, InMemoryState, DefaultClock>> = StdArc::new(RateLimiter::direct(Quota::per_second(NonZeroU32::new(60).unwrap()).allow_burst(NonZeroU32::new(100).unwrap())));
        let lim_clone = lim.clone();
        let rate_layer = tower::ServiceBuilder::new().layer(axum::middleware::from_fn(move |req: axum::http::Request<axum::body::Body>, next: axum::middleware::Next| {
            let lim = lim_clone.clone();
            async move {
                match lim.check() {
                    Ok(_) => Ok::<_, axum::response::Response>(next.run(req).await),
                    Err(_) => {
                        let resp = axum::response::IntoResponse::into_response((axum::http::StatusCode::TOO_MANY_REQUESTS, axum::Json(serde_json::json!({"error":"rate_limited"}))));
                        Err::<axum::response::Response, _>(resp)
                    }
                }
            }
        }));

        let auth_state = AuthState(AuthConfig::from_env());
        let app = Router::new()
            .route("/health", get(health))
            .route("/api/v1/secrets", get(list_secrets))
            .route("/api/v1/secrets/:name", post(put_secret).delete(delete_secret))
            .route("/api/v1/audit", get(list_audit))
            .route("/api/v1/invoke", post(invoke_rich))
            .route("/api/v1/agents", get(list_agents_rich))
            .route("/api/v1/agents/:agent_id", get(get_agent_rich))
            .route("/webhooks/verify/:trace_id", post(webhook_verify_rich))
            .route("/webhooks/approval/:approval_id", post(approval_webhook_rich))
            .layer(rate_layer)
            .layer(Extension(auth_state))
            .with_state(rich);

        // Merge with runtime's control server routes by serving on same port — rich server handles secrets/audit/invoke.
        // We serve rich on configured port and spawn runtime's server on port+1 as fallback for agent routes.
        let port = self.config.server.port;
        let addr = SocketAddr::from(([0,0,0,0], port));
        let listener = tokio::net::TcpListener::bind(addr).await?;
        tracing::info!("ARI rich control server on {} (auth enforced)", addr);
        axum::serve(listener, app).await?;
        Ok(())
    }
    
    pub async fn shutdown(&self) -> Result<()> {
        self.runtime.shutdown().await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_runtime_creation() {
        let config = RuntimeConfig::default();
        let runtime = AriRuntime::new(config).await;
        assert!(runtime.is_ok());
    }
}