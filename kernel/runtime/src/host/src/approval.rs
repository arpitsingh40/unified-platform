//! Approval workflow with control plane integration

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{RwLock, oneshot};
use tracing::{info, warn};
use uuid::Uuid;

use crate::governance::{ApprovalRequest, ApprovalStatus, ToolCall, GovernanceEngine};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalConfig {
    pub control_plane_url: String,
    pub api_key: String,
    pub default_timeout_seconds: u64,
    pub escalation_timeout_seconds: u64,
    pub auto_approve_threshold_usd: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalDetails {
    pub id: String,
    pub org_id: String,
    pub agent_id: String,
    pub action: String,
    pub summary: String,
    pub recommendation: String,
    pub estimated_cost_usd: f64,
    pub tool_calls: Vec<ToolCall>,
    pub status: ApprovalStatus,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub expires_at: chrono::DateTime<chrono::Utc>,
    pub resolved_at: Option<chrono::DateTime<chrono::Utc>>,
    pub resolved_by: Option<String>,
    pub modifications: Option<serde_json::Value>,
    pub approvers_notified: Vec<String>,
    pub required_approvers: u32,
    pub current_approvals: u32,
}

pub struct ApprovalEngine {
    config: ApprovalConfig,
    governance: Arc<GovernanceEngine>,
    pending: Arc<RwLock<HashMap<String, oneshot::Sender<ApprovalResult>>>>,
    http_client: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalResult {
    pub approved: bool,
    pub approval_id: String,
    pub resolved_by: Option<String>,
    pub modifications: Option<serde_json::Value>,
    pub resolved_at: chrono::DateTime<chrono::Utc>,
}

impl ApprovalEngine {
    pub fn new(config: ApprovalConfig, governance: Arc<GovernanceEngine>) -> Self {
        Self {
            config,
            governance,
            pending: Arc::new(RwLock::new(HashMap::new())),
            http_client: reqwest::Client::new(),
        }
    }
    
    pub async fn request_approval(
        &self,
        org_id: &str,
        agent_id: &str,
        action: &str,
        summary: &str,
        recommendation: &str,
        estimated_cost: f64,
        tool_calls: Vec<ToolCall>,
        required_approvers: u32,
    ) -> Result<ApprovalResult> {
        // Check auto-approve threshold
        if estimated_cost <= self.config.auto_approve_threshold_usd {
            info!("Auto-approving: ${:.2} <= ${:.2}", estimated_cost, self.config.auto_approve_threshold_usd);
            return Ok(ApprovalResult {
                approved: true,
                approval_id: Uuid::new_v4().to_string(),
                resolved_by: Some("auto-approve".to_string()),
                modifications: None,
                resolved_at: chrono::Utc::now(),
            });
        }
        
        // Create approval request
        let approval_id = Uuid::new_v4().to_string();
        let now = chrono::Utc::now();
        let expires_at = now + chrono::Duration::seconds(self.config.default_timeout_seconds as i64);
        
        let request = ApprovalDetails {
            id: approval_id.clone(),
            org_id: org_id.to_string(),
            agent_id: agent_id.to_string(),
            action: action.to_string(),
            summary: summary.to_string(),
            recommendation: recommendation.to_string(),
            estimated_cost_usd: estimated_cost,
            tool_calls,
            status: ApprovalStatus::Pending,
            created_at: now,
            expires_at,
            resolved_at: None,
            resolved_by: None,
            modifications: None,
            approvers_notified: vec![],
            required_approvers,
            current_approvals: 0,
        };
        
        // Persist to governance
        self.governance.persist_approval(&ApprovalRequest {
            id: approval_id.clone(),
            org_id: org_id.to_string(),
            agent_id: agent_id.to_string(),
            action: action.to_string(),
            summary: summary.to_string(),
            recommendation: recommendation.to_string(),
            estimated_cost_usd: estimated_cost,
            tool_calls: request.tool_calls.clone(),
            status: ApprovalStatus::Pending,
            created_at: now,
            resolved_at: None,
            resolved_by: None,
            modifications: None,
        }).await?;
        
        // Notify control plane
        self.notify_control_plane(&request).await?;
        
        // Wait for resolution
        let (tx, rx) = oneshot::channel();
        self.pending.write().await.insert(approval_id.clone(), tx);
        
        let timeout = Duration::from_secs(self.config.default_timeout_seconds);
        
        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(result)) => Ok(result),
            Ok(Err(_)) => {
                // Channel closed
                self.handle_timeout(&approval_id).await?;
                Ok(ApprovalResult {
                    approved: false,
                    approval_id,
                    resolved_by: None,
                    modifications: None,
                    resolved_at: chrono::Utc::now(),
                })
            }
            Err(_) => {
                // Timeout - escalate
                self.handle_timeout(&approval_id).await?;
                Ok(ApprovalResult {
                    approved: false,
                    approval_id,
                    resolved_by: None,
                    modifications: None,
                    resolved_at: chrono::Utc::now(),
                })
            }
        }
    }
    
    async fn notify_control_plane(&self, request: &ApprovalDetails) -> Result<()> {
        let url = format!("{}/api/v1/approvals", self.config.control_plane_url);
        
        let payload = serde_json::json!({
            "approval_id": request.id,
            "org_id": request.org_id,
            "agent_id": request.agent_id,
            "action": request.action,
            "summary": request.summary,
            "recommendation": request.recommendation,
            "estimated_cost_usd": request.estimated_cost_usd,
            "tool_calls": request.tool_calls,
            "required_approvers": request.required_approvers,
            "expires_at": request.expires_at.to_rfc3339(),
        });
        
        let resp = self.http_client
            .post(&url)
            .bearer_auth(&self.config.api_key)
            .json(&payload)
            .send()
            .await?;
        
        if !resp.status().is_success() {
            warn!("Failed to notify control plane: {}", resp.status());
        }
        
        Ok(())
    }
    
    async fn handle_timeout(&self, approval_id: &str) -> Result<()> {
        // Escalate to founder / admin
        let escalation_url = format!("{}/api/v1/approvals/{}/escalate", 
            self.config.control_plane_url, approval_id);
        
        let _ = self.http_client
            .post(&escalation_url)
            .bearer_auth(&self.config.api_key)
            .send()
            .await;
        
        // Mark as expired in governance
        // (would need a method on governance engine)
        
        Ok(())
    }
    
    pub async fn resolve_approval(
        &self,
        approval_id: &str,
        approved: bool,
        resolved_by: &str,
        modifications: Option<serde_json::Value>,
    ) -> Result<()> {
        let mut pending = self.pending.write().await;
        
        if let Some(tx) = pending.remove(approval_id) {
            let result = ApprovalResult {
                approved,
                approval_id: approval_id.to_string(),
                resolved_by: Some(resolved_by.to_string()),
                modifications: modifications.clone(),
                resolved_at: chrono::Utc::now(),
            };
            
            let _ = tx.send(result);
        }
        
        // Update governance
        self.governance.resolve_approval(approval_id, approved, resolved_by, modifications.clone()).await?;
        
        // Notify control plane
        let url = format!("{}/api/v1/approvals/{}/resolve", self.config.control_plane_url, approval_id);
        let payload = serde_json::json!({
            "approved": approved,
            "resolved_by": resolved_by,
            "modifications": modifications.clone(),
        });
        
        let _ = self.http_client
            .post(&url)
            .bearer_auth(&self.config.api_key)
            .json(&payload)
            .send()
            .await;
        
        Ok(())
    }
    
    pub async fn get_pending_approvals(&self, org_id: &str) -> Result<Vec<ApprovalDetails>> {
        // Query governance for pending approvals
        // This would be implemented in the governance engine
        Ok(vec![])
    }
    
    pub async fn cancel_approval(&self, approval_id: &str, reason: &str) -> Result<()> {
        let mut pending = self.pending.write().await;
        
        if let Some(tx) = pending.remove(approval_id) {
            let result = ApprovalResult {
                approved: false,
                approval_id: approval_id.to_string(),
                resolved_by: Some("cancelled".to_string()),
                modifications: Some(serde_json::json!({ "reason": reason })),
                resolved_at: chrono::Utc::now(),
            };
            
            let _ = tx.send(result);
        }
        
        Ok(())
    }
}