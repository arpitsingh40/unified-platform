//! Core runtime - WASM component loading, fuel metering, execution

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{RwLock, Semaphore};
use tracing::{debug, info, warn, error};
use uuid::Uuid;

use wasmtime::{Engine, Store, Linker, component::{Component, ResourceTable}};
use wasmtime_wasi::{WasiCtx, WasiCtxBuilder, WasiView};

use crate::config::RuntimeEngineConfig;
use crate::capabilities::CapabilityRegistry;
use crate::governance::GovernanceEngine;
use crate::memory::MemoryManager;
use crate::verification::VerificationEngine;
use crate::approval::ApprovalEngine;
use crate::identity::IdentityManager;
use crate::metrics::MetricsCollector;

// Import generated bindings
// wit_bindgen::generate!({
//     path: "../wit",
//     world: "agent",
//     with: {
//         "ari:runtime/json": serde_json::Value,
//     },
// });

#[derive(Clone)]
pub struct AgentInstance {
    pub agent_id: String,
    pub org_id: String,
    pub component: Component,
    pub metadata: AgentMetadata,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub invocation_count: u64,
    pub total_cost_usd: f64,
    pub last_invocation: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentMetadata {
    pub name: String,
    pub version: String,
    pub spec_version: String,
    pub capabilities: Vec<String>,
    pub authority: String,
    pub schedule: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvocationRequest {
    pub invocation_id: String,
    pub agent_id: String,
    pub org_id: String,
    pub context: serde_json::Value,
    pub trace_parent: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvocationResult {
    pub invocation_id: String,
    pub agent_id: String,
    pub success: bool,
    pub decision: Option<AgentDecision>,
    pub executions: Vec<ExecutionRecord>,
    pub verification: Vec<VerificationRecord>,
    pub total_cost_usd: f64,
    pub total_time_ms: u64,
    pub error: Option<String>,
    pub completed_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDecision {
    pub action: String,
    pub reasoning: String,
    pub tool_calls: Vec<ToolCall>,
    pub confidence: f64,
    pub review_after_days: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    pub capability: String,
    pub tool: String,
    pub args: serde_json::Value,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionRecord {
    pub capability: String,
    pub tool: String,
    pub args: serde_json::Value,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
    pub execution_time_ms: u64,
    pub cost_usd: f64,
    pub verified: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationRecord {
    pub capability: String,
    pub outcome: String,
    pub confidence: f64,
    pub insight: String,
}

pub struct AgentRuntime {
    config: RuntimeEngineConfig,
    engine: Engine,
    components: Arc<RwLock<HashMap<String, AgentInstance>>>,
    capability_registry: Arc<CapabilityRegistry>,
    pub governance: Arc<GovernanceEngine>,
    memory: Arc<MemoryManager>,
    pub verification: Arc<VerificationEngine>,
    approval: Arc<ApprovalEngine>,
    identity: Arc<IdentityManager>,
    metrics: Arc<MetricsCollector>,
    semaphore: Arc<Semaphore>,
    fuel_limit: u64,
}

impl AgentRuntime {
    pub async fn new(
        config: RuntimeEngineConfig,
        capability_registry: Arc<CapabilityRegistry>,
        governance: Arc<GovernanceEngine>,
        memory: Arc<MemoryManager>,
        verification: Arc<VerificationEngine>,
        approval: Arc<ApprovalEngine>,
        identity: Arc<IdentityManager>,
        metrics: Arc<MetricsCollector>,
    ) -> Result<Self> {
        // Create Wasmtime engine with component model
        let mut wasmtime_config = wasmtime::Config::new();
        wasmtime_config.wasm_component_model(true);
        wasmtime_config.async_support(true);
        
        if let Some(fuel) = config.fuel_limit {
            wasmtime_config.consume_fuel(true);
        }
        
        if config.epoch_interruption {
            wasmtime_config.epoch_interruption(true);
        }
        
        let engine = Engine::new(&wasmtime_config)?;
        
        let semaphore = Arc::new(Semaphore::new(config.max_concurrent_agents));
        
        let fuel_limit = config.fuel_limit.unwrap_or(10_000_000);
        Ok(Self {
            config: config.clone(),
            engine,
            components: Arc::new(RwLock::new(HashMap::new())),
            capability_registry,
            governance,
            memory,
            verification,
            approval,
            identity,
            metrics,
            semaphore,
            fuel_limit,
        })
    }
    
    pub async fn load_agent(&self, agent_id: &str, component_path: &PathBuf, metadata: AgentMetadata) -> Result<()> {
        let component = Component::from_file(&self.engine, component_path)
            .context("Failed to load WASM component")?;
        
        let instance = AgentInstance {
            agent_id: agent_id.to_string(),
            org_id: metadata.capabilities.first().cloned().unwrap_or_default(), // placeholder
            component,
            metadata,
            created_at: chrono::Utc::now(),
            invocation_count: 0,
            total_cost_usd: 0.0,
            last_invocation: None,
        };
        
        self.components.write().await.insert(agent_id.to_string(), instance);
        info!("Loaded agent: {}", agent_id);
        
        Ok(())
    }
    
    pub async fn invoke(&self, request: InvocationRequest) -> Result<InvocationResult> {
        let start = Instant::now();
        let invocation_id = request.invocation_id.clone();
        
        // Acquire semaphore for concurrency control
        let _permit = self.semaphore.acquire().await?;
        
        // Get agent instance
        let instance = {
            let components = self.components.read().await;
            components.get(&request.agent_id).cloned()
                .ok_or_else(|| anyhow::anyhow!("Agent not found: {}", request.agent_id))?
        };
        
        // Check governance
        let estimated_cost = 0.01; // Would be estimated from context
        let gate = self.governance.check_execution(&request.org_id, &request.agent_id, estimated_cost).await?;
        
        match gate {
            crate::governance::ExecutionGate::Blocked(reason) => {
                return Ok(InvocationResult {
                    invocation_id,
                    agent_id: request.agent_id,
                    success: false,
                    decision: None,
                    executions: vec![],
                    verification: vec![],
                    total_cost_usd: 0.0,
                    total_time_ms: start.elapsed().as_millis() as u64,
                    error: Some(reason),
                    completed_at: chrono::Utc::now(),
                });
            }
            crate::governance::ExecutionGate::DryRun => {
                // Run but don't execute capabilities
                return self.invoke_dry_run(instance, request, start).await;
            }
            crate::governance::ExecutionGate::Allowed => {}
        }
        
        // Prepare agent input
        let capabilities = self.capability_registry.list_capabilities().await;
        let granted_capabilities: Vec<_> = capabilities.into_iter()
            .filter(|c| instance.metadata.capabilities.contains(&c.id))
            .collect();
        
        let limits = crate::governance::ResourceLimits {
            max_execution_time_ms: self.config.default_execution_timeout_ms,
            max_memory_mb: self.config.default_memory_limit_mb,
            max_tool_calls: 20,
            max_cost_usd: 1.0,
        };
        
        let governance_state = crate::governance::GovernanceState {
            kill_switch: false,
            dry_run: false,
            weekly_spend_cap_usd: 100.0,
            weekly_spend_used_usd: 0.0,
            weekly_period_start: chrono::Utc::now(),
            org_overrides: HashMap::new(),
        };
        
        // In a real implementation, we'd call the WASM component's `run` export
        // For now, simulate the execution
        let result = self.execute_agent_logic(
            &instance,
            &request,
            &granted_capabilities,
            &limits,
            &governance_state,
            start,
        ).await?;
        
        // Update metrics
        self.metrics.record_invocation(&result).await;
        
        // Update instance stats
        self.update_instance_stats(&request.agent_id, &result).await?;
        
        Ok(result)
    }
    
    async fn invoke_dry_run(&self, instance: AgentInstance, request: InvocationRequest, start: Instant) -> Result<InvocationResult> {
        // Simulate execution without calling capabilities
        info!("Dry run for agent: {}", request.agent_id);
        
        Ok(InvocationResult {
            invocation_id: request.invocation_id,
            agent_id: request.agent_id,
            success: true,
            decision: Some(AgentDecision {
                action: "DRY_RUN".to_string(),
                reasoning: "Dry run mode - no capabilities executed".to_string(),
                tool_calls: vec![],
                confidence: 1.0,
                review_after_days: 1,
            }),
            executions: vec![],
            verification: vec![],
            total_cost_usd: 0.0,
            total_time_ms: start.elapsed().as_millis() as u64,
            error: None,
            completed_at: chrono::Utc::now(),
        })
    }
    
    async fn execute_agent_logic(
        &self,
        instance: &AgentInstance,
        request: &InvocationRequest,
        capabilities: &[crate::capabilities::Capability],
        limits: &crate::governance::ResourceLimits,
        governance: &crate::governance::GovernanceState,
        start: Instant,
    ) -> Result<InvocationResult> {
        // In production, this would:
        // 1. Create a Store with WASI context
        // 2. Link host functions (execute-capability, log, metric, memory-*, etc.)
        // 3. Instantiate the component
        // 4. Call the `run` export with AgentInput
        // 5. Parse AgentResult
        
        // For now, simulate the agent decision-making
        let decision = self.simulate_agent_decision(instance, request, capabilities).await?;
        
        // Execute tool calls — L3 gate: approval for anything not reversible.
        // Decision for demo uses sales_agent::decide which emits:
        //   crm.read::crm.query (L3 auto) + email.send::email.send (approval-gated)
        // We enforce here: `email.send` requires governance approval if org demands it.
        let mut executions = Vec::new();
        let mut total_cost = 0.0;
        let mut pending_approvals: Vec<String> = vec![];

        for tool_call in &decision.tool_calls {
            let needs_approval = matches!(tool_call.capability.as_str(), "email.send" | "crm.write" | "document.generate" | "calendar.schedule");
            if needs_approval {
                // Check via governance: does this org require approval for this action?
                // For the offline demo, treat email.send as approval-gated per agent.yaml.
                let app = self.governance.request_approval(
                    &request.org_id, &request.agent_id,
                    &tool_call.capability, &tool_call.reason, &tool_call.reason, 0.01,
                    vec![crate::governance::ToolCall { capability: tool_call.capability.clone(), tool: tool_call.tool.clone(), args: tool_call.args.clone(), reason: tool_call.reason.clone() }],
                ).await?;
                match app {
                    crate::governance::ApprovalResponse::Pending(id) => {
                        pending_approvals.push(id.clone());
                        executions.push(ExecutionRecord {
                            capability: tool_call.capability.clone(),
                            tool: tool_call.tool.clone(),
                            args: tool_call.args.clone(),
                            result: Some(serde_json::json!({"status":"pending_approval","approval_id": id})),
                            error: None,
                            execution_time_ms: 0,
                            cost_usd: 0.0,
                            verified: false,
                        });
                        continue;
                    }
                    crate::governance::ApprovalResponse::AutoApproved | crate::governance::ApprovalResponse::Approved(_) => {}
                    crate::governance::ApprovalResponse::Denied(reason) => {
                        executions.push(ExecutionRecord {
                            capability: tool_call.capability.clone(), tool: tool_call.tool.clone(), args: tool_call.args.clone(),
                            result: None, error: Some(format!("denied: {}", reason)), execution_time_ms: 0, cost_usd: 0.0, verified: false,
                        });
                        continue;
                    }
                    _ => {}
                }
            }
            let cap_request = crate::capabilities::CapabilityRequest {
                capability: tool_call.capability.clone(),
                tool: tool_call.tool.clone(),
                args: tool_call.args.clone(),
                reason: tool_call.reason.clone(),
                trace_id: request.invocation_id.clone(),
                idempotency_key: Some(Uuid::new_v4().to_string()),
            };
            let cap_response = self.capability_registry.execute(cap_request).await?;
            executions.push(ExecutionRecord {
                capability: tool_call.capability.clone(),
                tool: tool_call.tool.clone(),
                args: tool_call.args.clone(),
                result: cap_response.result.clone(),
                error: cap_response.error.clone(),
                execution_time_ms: cap_response.execution_time_ms,
                cost_usd: cap_response.cost_usd,
                verified: false,
            });
            total_cost += cap_response.cost_usd;
        }
        
        // Verify executions
        let mut verification = Vec::new();
        for exec in &executions {
            if let Some(ref result) = exec.result {
                let verify_request = crate::verification::VerificationRequest {
                    capability: exec.capability.clone(),
                    tool: exec.tool.clone(),
                    expected: "success".to_string(),
                    actual: result.clone(),
                    trace_id: request.invocation_id.clone(),
                    config: crate::verification::VerificationConfig {
                        method: crate::verification::VerificationMethod::ReadBack { field: "status".to_string() },
                        timeout_seconds: 30,
                        expected_pattern: None,
                        webhook_url: None,
                        webhook_secret: None,
                        approver_roles: vec![],
                    },
                };
                
                let verify_result = self.verification.verify(verify_request).await?;
                
                verification.push(VerificationRecord {
                    capability: exec.capability.clone(),
                    outcome: format!("{:?}", verify_result.outcome),
                    confidence: verify_result.confidence,
                    insight: verify_result.insight,
                });
            }
        }
        
        // Record spend
        if total_cost > 0.0 {
            self.governance.record_spend(&request.org_id, total_cost).await?;
        }
        
        Ok(InvocationResult {
            invocation_id: request.invocation_id.clone(),
            agent_id: request.agent_id.clone(),
            success: true,
            decision: Some(decision),
            executions,
            verification,
            total_cost_usd: total_cost,
            total_time_ms: start.elapsed().as_millis() as u64,
            error: None,
            completed_at: chrono::Utc::now(),
        })
    }
    
    async fn simulate_agent_decision(
        &self,
        instance: &AgentInstance,
        request: &InvocationRequest,
        _capabilities: &[crate::capabilities::Capability],
    ) -> Result<AgentDecision> {
        // Enterprise wedge: delegate to the real sales-agent crate's pure function.
        // In production the WASM component makes this decision; this path is used for
        // native fallback and for demos without a loaded Component.
        use sales_agent::decide;
        let d = decide(&request.context);
        Ok(AgentDecision {
            action: d.action,
            reasoning: format!("[{}] {}", instance.agent_id, d.reasoning),
            tool_calls: d.tool_calls.into_iter().map(|tc| ToolCall {
                capability: tc.capability,
                tool: tc.tool,
                args: tc.args,
                reason: tc.reason,
            }).collect(),
            confidence: d.confidence,
            review_after_days: d.review_after_days,
        })
    }
    
    async fn update_instance_stats(&self, agent_id: &str, result: &InvocationResult) -> Result<()> {
        let mut components = self.components.write().await;
        if let Some(instance) = components.get_mut(agent_id) {
            instance.invocation_count += 1;
            instance.total_cost_usd += result.total_cost_usd;
            instance.last_invocation = Some(result.completed_at);
        }
        Ok(())
    }
    
    pub async fn get_agent(&self, agent_id: &str) -> Option<AgentInstance> {
        self.components.read().await.get(agent_id).cloned()
    }
    
    pub async fn list_agents(&self) -> Vec<AgentInstance> {
        self.components.read().await.values().cloned().collect()
    }
    
    pub async fn unload_agent(&self, agent_id: &str) -> Result<()> {
        self.components.write().await.remove(agent_id);
        info!("Unloaded agent: {}", agent_id);
        Ok(())
    }
    
    pub async fn background_tasks(&self) {
        let mut interval = tokio::time::interval(Duration::from_secs(60));
        
        loop {
            interval.tick().await;
            
            // Increment epoch for interruption
            if self.config.epoch_interruption {
                self.engine.increment_epoch();
            }
            
            // Cleanup expired memory
            if let Err(e) = self.memory.cleanup_expired().await {
                warn!("Memory cleanup failed: {}", e);
            }
            
            // Update metrics
            self.metrics.flush().await;
        }
    }
    
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down runtime...");
        self.components.write().await.clear();
        Ok(())
    }
}

pub async fn start_control_server(runtime: Arc<AgentRuntime>) -> Result<()> {
    use axum::{Router, routing::{get, post}, Json, extract::{State, Path}, Extension};
    use std::net::SocketAddr;
    use crate::auth::{AuthState, AuthConfig, AuthenticatedUser};

    #[derive(Clone)]
    struct AppState { runtime: Arc<AgentRuntime> }

    async fn health() -> Json<serde_json::Value> {
        Json(serde_json::json!({"status":"ok","service":"ari-runtime-host"}))
    }
    async fn invoke_handler(
        auth: AuthenticatedUser,
        State(state): State<AppState>,
        Json(mut request): Json<InvocationRequest>,
    ) -> Result<Json<InvocationResult>, axum::http::StatusCode> {
        crate::tenancy::assert_tenant(&auth.org_id, &request.org_id).map_err(|_| axum::http::StatusCode::FORBIDDEN)?;
        // ensure trace_id
        if request.trace_parent.is_none() {
            request.trace_parent = Some(crate::audit::trace_parent_header(&request.invocation_id));
        }
        state.runtime.invoke(request).await.map(Json).map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)
    }
    async fn list_agents(auth: AuthenticatedUser, State(state): State<AppState>) -> Json<Vec<serde_json::Value>> {
        let agents = state.runtime.list_agents().await;
        // filter to caller's org (tenant isolation at list time)
        Json(agents.into_iter().filter(|a| a.org_id == auth.org_id).map(|a| serde_json::json!({"agent_id": a.agent_id, "org_id": a.org_id, "metadata": a.metadata})).collect())
    }
    async fn get_agent(auth: AuthenticatedUser, State(state): State<AppState>, Path(agent_id): Path<String>) -> Result<Json<serde_json::Value>, axum::http::StatusCode> {
        let a = state.runtime.get_agent(&agent_id).await.ok_or(axum::http::StatusCode::NOT_FOUND)?;
        if a.org_id != auth.org_id { return Err(axum::http::StatusCode::FORBIDDEN); }
        Ok(Json(serde_json::json!({"agent_id": a.agent_id, "org_id": a.org_id, "metadata": a.metadata, "created_at": a.created_at, "invocation_count": a.invocation_count, "total_cost_usd": a.total_cost_usd})))
    }
    async fn audit_list_handler(auth: AuthenticatedUser, State(_state): State<AppState>) -> Json<serde_json::Value> {
        Json(serde_json::json!({"org_id": auth.org_id, "entries": []}))
    }
    async fn webhook_verify_handler(
        Path(trace_id): Path<String>,
        headers: axum::http::HeaderMap,
        State(state): State<AppState>,
        body: axum::body::Bytes,
    ) -> Result<Json<serde_json::Value>, axum::http::StatusCode> {
        let sig = headers.get("x-webhook-signature").or_else(|| headers.get("x-hub-signature-256")).and_then(|v| v.to_str().ok());
        // secret lookup: WEBHOOK_SECRET env or per-trace config; for now use global env
        let secret = std::env::var("ARI_WEBHOOK_SECRET").ok();
        if !crate::verification::VerificationEngine::verify_webhook_signature(&body, sig, secret.as_deref()) {
            return Err(axum::http::StatusCode::UNAUTHORIZED);
        }
        let payload: serde_json::Value = serde_json::from_slice(&body).map_err(|_| axum::http::StatusCode::BAD_REQUEST)?;
        state.runtime.verification.handle_webhook_callback(&trace_id, payload).await.map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)?;
        Ok(Json(serde_json::json!({"ok": true, "trace_id": trace_id})))
    }
    async fn approval_webhook_handler(
        Path(approval_id): Path<String>,
        State(state): State<AppState>,
        Json(payload): Json<serde_json::Value>,
    ) -> Result<Json<serde_json::Value>, axum::http::StatusCode> {
        let approved = payload.get("approved").and_then(|v| v.as_bool()).unwrap_or(false);
        let reviewer = payload.get("reviewer").and_then(|v| v.as_str()).unwrap_or("webhook");
        let mods = payload.get("modifications").cloned();
        state.runtime.verification.handle_approval_callback(&approval_id, approved, reviewer, mods).await.map_err(|_| axum::http::StatusCode::INTERNAL_SERVER_ERROR)?;
        // also resolve via governance for persistence
        let _ = state.runtime.governance.resolve_approval(&approval_id, approved, reviewer, payload.get("modifications").cloned()).await;
        Ok(Json(serde_json::json!({"ok": true, "approval_id": approval_id, "approved": approved})))
    }
    async fn metrics_handler(State(state): State<AppState>) -> String {
        let _ = &state;
        String::new()
    }

    let auth_state = AuthState(AuthConfig::from_env());
    let app = Router::new()
        .route("/health", get(health))
        .route("/metrics", get(metrics_handler))
        .route("/api/v1/invoke", post(invoke_handler))
        .route("/api/v1/agents", get(list_agents))
        .route("/api/v1/agents/:agent_id", get(get_agent))
        .route("/api/v1/audit", get(audit_list_handler))
        .route("/webhooks/verify/:trace_id", post(webhook_verify_handler))
        .route("/webhooks/approval/:approval_id", post(approval_webhook_handler))
        .layer(Extension(auth_state))
        .with_state(AppState { runtime });

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    let listener = tokio::net::TcpListener::bind(addr).await?;
    info!("Control server listening on {} (auth enforced, /health public)", addr);
    axum::serve(listener, app).await?;
    Ok(())
}