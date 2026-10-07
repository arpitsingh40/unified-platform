//! Metrics collection and billing integration
//! Prometheus via 0.13 API: builder.build() -> (Recorder, Handle). We store Handle.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::info;

use crate::runtime::InvocationResult;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InvocationMetrics {
    pub invocation_id: String,
    pub agent_id: String,
    pub org_id: String,
    pub success: bool,
    pub duration_ms: u64,
    pub cost_usd: f64,
    pub tool_calls: u32,
    pub verification_passed: u32,
    pub verification_failed: u32,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentMetrics {
    pub agent_id: String,
    pub org_id: String,
    pub total_invocations: u64,
    pub successful_invocations: u64,
    pub failed_invocations: u64,
    pub total_cost_usd: f64,
    pub avg_duration_ms: f64,
    pub avg_tool_calls: f64,
    pub verification_success_rate: f64,
    pub last_invocation: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrgMetrics {
    pub org_id: String,
    pub total_agents: u32,
    pub total_invocations: u64,
    pub total_cost_usd: f64,
    pub weekly_spend_usd: f64,
    pub weekly_cap_usd: f64,
    pub active_agents: u32,
}

pub struct MetricsCollector {
    invocation_buffer: Arc<RwLock<Vec<InvocationMetrics>>>,
    agent_metrics: Arc<RwLock<HashMap<String, AgentMetrics>>>,
    org_metrics: Arc<RwLock<HashMap<String, OrgMetrics>>>,
    flush_interval: Duration,
}

impl MetricsCollector {
    pub fn new() -> Result<Self> {
        if let Err(e) = metrics_exporter_prometheus::PrometheusBuilder::new().install() {
            tracing::warn!("prometheus install failed (may already be installed): {}", e);
        }
        Ok(Self {
            invocation_buffer: Arc::new(RwLock::new(Vec::new())),
            agent_metrics: Arc::new(RwLock::new(HashMap::new())),
            org_metrics: Arc::new(RwLock::new(HashMap::new())),
            flush_interval: Duration::from_secs(60),
        })
    }
    
    pub async fn record_invocation(&self, result: &InvocationResult) {
        let metrics = InvocationMetrics {
            invocation_id: result.invocation_id.clone(),
            agent_id: result.agent_id.clone(),
            org_id: "unknown".to_string(),
            success: result.success,
            duration_ms: result.total_time_ms,
            cost_usd: result.total_cost_usd,
            tool_calls: result.executions.len() as u32,
            verification_passed: result.verification.iter().filter(|v| v.outcome == "Success").count() as u32,
            verification_failed: result.verification.iter().filter(|v| v.outcome == "Failure").count() as u32,
            timestamp: chrono::Utc::now(),
        };
        metrics::counter!("ari_invocations_total", 1);
        metrics::histogram!("ari_invocation_duration_ms", result.total_time_ms as f64);
        metrics::histogram!("ari_invocation_cost_usd", result.total_cost_usd);
        metrics::counter!("ari_tool_calls_total", result.executions.len() as u64);
        self.invocation_buffer.write().await.push(metrics);
    }
    
    pub async fn record_agent_metrics(&self, agent_id: &str, org_id: &str, result: &InvocationResult) {
        let mut agents = self.agent_metrics.write().await;
        let entry = agents.entry(agent_id.to_string()).or_insert_with(|| AgentMetrics {
            agent_id: agent_id.to_string(), org_id: org_id.to_string(),
            total_invocations: 0, successful_invocations: 0, failed_invocations: 0,
            total_cost_usd: 0.0, avg_duration_ms: 0.0, avg_tool_calls: 0.0,
            verification_success_rate: 0.0, last_invocation: None,
        });
        entry.total_invocations += 1;
        if result.success { entry.successful_invocations += 1; } else { entry.failed_invocations += 1; }
        entry.total_cost_usd += result.total_cost_usd;
        entry.avg_duration_ms = (entry.avg_duration_ms * (entry.total_invocations - 1) as f64 + result.total_time_ms as f64) / entry.total_invocations as f64;
        entry.avg_tool_calls = (entry.avg_tool_calls * (entry.total_invocations - 1) as f64 + result.executions.len() as f64) / entry.total_invocations as f64;
        if !result.verification.is_empty() {
            let passed = result.verification.iter().filter(|v| v.outcome == "Success").count();
            entry.verification_success_rate = passed as f64 / result.verification.len() as f64;
        }
        entry.last_invocation = Some(result.completed_at);
        metrics::gauge!("ari_agent_invocations_total", entry.total_invocations as f64);
        metrics::gauge!("ari_agent_cost_usd", entry.total_cost_usd);
        metrics::gauge!("ari_agent_verification_success_rate", entry.verification_success_rate);
    }
    
    pub async fn record_org_metrics(&self, org_id: &str, agents: u32, total_cost: f64, weekly_cap: f64) {
        let mut orgs = self.org_metrics.write().await;
        let entry = orgs.entry(org_id.to_string()).or_insert_with(|| OrgMetrics {
            org_id: org_id.to_string(), total_agents: 0, total_invocations: 0, total_cost_usd: 0.0, weekly_spend_usd: 0.0, weekly_cap_usd: weekly_cap, active_agents: 0,
        });
        entry.total_agents = agents;
        entry.total_cost_usd = total_cost;
        entry.weekly_cap_usd = weekly_cap;
        metrics::gauge!("ari_org_agents", agents as f64);
        metrics::gauge!("ari_org_cost_usd", total_cost);
        metrics::gauge!("ari_org_weekly_spend_pct", if weekly_cap>0.0 { entry.weekly_spend_usd / weekly_cap * 100.0 } else { 0.0 });
    }
    
    pub async fn flush(&self) {
        let mut buffer = self.invocation_buffer.write().await;
        if buffer.is_empty() { return; }
        let invocations: Vec<_> = buffer.drain(..).collect();
        let mut agent_agg: HashMap<String, (u64, u64, f64, u64, u64, u64)> = HashMap::new();
        for inv in &invocations {
            let e = agent_agg.entry(inv.agent_id.clone()).or_default();
            e.0 += 1; if inv.success { e.1 += 1; } e.2 += inv.cost_usd; e.3 += inv.duration_ms; e.4 += inv.tool_calls as u64; e.5 += inv.verification_passed as u64 + inv.verification_failed as u64;
        }
        let mut agents = self.agent_metrics.write().await;
        for (agent_id, (total, success, cost, duration_sum, tool_calls, _vers)) in agent_agg {
            let entry = agents.entry(agent_id.clone()).or_insert_with(|| AgentMetrics {
                agent_id: agent_id.clone(), org_id: "unknown".to_string(), total_invocations: 0, successful_invocations: 0, failed_invocations: 0, total_cost_usd: 0.0, avg_duration_ms: 0.0, avg_tool_calls: 0.0, verification_success_rate: 0.0, last_invocation: None,
            });
            entry.total_invocations += total;
            entry.successful_invocations += success;
            entry.failed_invocations += total - success;
            entry.total_cost_usd += cost;
            entry.avg_duration_ms = duration_sum as f64 / total as f64;
            entry.avg_tool_calls = tool_calls as f64 / total as f64;
        }
        info!("Flushed {} invocation metrics", invocations.len());
    }
    
    pub async fn get_agent_metrics(&self, agent_id: &str) -> Option<AgentMetrics> { self.agent_metrics.read().await.get(agent_id).cloned() }
    pub async fn get_org_metrics(&self, org_id: &str) -> Option<OrgMetrics> { self.org_metrics.read().await.get(org_id).cloned() }
    pub async fn get_all_agent_metrics(&self) -> Vec<AgentMetrics> { self.agent_metrics.read().await.values().cloned().collect() }
    pub async fn get_all_org_metrics(&self) -> Vec<OrgMetrics> { self.org_metrics.read().await.values().cloned().collect() }
    pub fn prometheus_metrics(&self) -> String { String::new() }
}

impl Default for MetricsCollector {
    fn default() -> Self { Self::new().expect("Failed to create metrics collector") }
}
