//! Outcome verification - read-back, webhook, human review

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{RwLock, oneshot};
use tracing::{debug, info, warn};

use crate::capabilities::VerificationOutcome;
use crate::governance::GovernanceEngine;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationConfig {
    pub method: VerificationMethod,
    pub timeout_seconds: u64,
    pub expected_pattern: Option<String>,
    pub webhook_url: Option<String>,
    pub webhook_secret: Option<String>,
    pub approver_roles: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum VerificationMethod {
    ReadBack { field: String },
    Webhook { events: Vec<String> },
    HumanReview { required_approvers: u32 },
    Custom { handler: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationRequest {
    pub capability: String,
    pub tool: String,
    pub expected: String,
    pub actual: serde_json::Value,
    pub trace_id: String,
    pub config: VerificationConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    pub outcome: VerificationOutcome,
    pub confidence: f64,
    pub insight: String,
    pub verified_at: chrono::DateTime<chrono::Utc>,
    pub method: VerificationMethod,
    pub evidence: Vec<VerificationEvidence>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationEvidence {
    pub source: String,
    pub data: serde_json::Value,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

pub struct VerificationEngine {
    governance: Arc<GovernanceEngine>,
    pending_webhooks: Arc<RwLock<HashMap<String, oneshot::Sender<VerificationResult>>>>,
    pending_reviews: Arc<RwLock<HashMap<String, oneshot::Sender<VerificationResult>>>>,
    http_client: reqwest::Client,
}

impl VerificationEngine {
    pub fn new(governance: Arc<GovernanceEngine>) -> Self {
        Self {
            governance,
            pending_webhooks: Arc::new(RwLock::new(HashMap::new())),
            pending_reviews: Arc::new(RwLock::new(HashMap::new())),
            http_client: reqwest::Client::new(),
        }
    }
    
    pub async fn verify(&self, request: VerificationRequest) -> Result<VerificationResult> {
        let start = Instant::now();
        
        match request.config.method {
            VerificationMethod::ReadBack { ref field } => {
                self.verify_read_back(&request, &field).await
            }
            VerificationMethod::Webhook { ref events } => {
                self.verify_webhook(&request, &events).await
            }
            VerificationMethod::HumanReview { required_approvers } => {
                self.verify_human_review(&request, required_approvers).await
            }
            VerificationMethod::Custom { ref handler } => {
                self.verify_custom(&request, &handler).await
            }
        }
    }
    
    async fn verify_read_back(&self, request: &VerificationRequest, field: &str) -> Result<VerificationResult> {
        // The actual result is already in request.actual
        // We compare expected vs actual
        let expected = &request.expected;
        let actual = &request.actual;
        
        let (outcome, confidence, insight) = self.compare_values(expected, actual, field);
        
        Ok(VerificationResult {
            outcome,
            confidence,
            insight,
            verified_at: chrono::Utc::now(),
            method: request.config.method.clone(),
            evidence: vec![
                VerificationEvidence {
                    source: "read_back".to_string(),
                    data: serde_json::json!({
                        "expected": expected,
                        "actual": actual,
                        "field": field
                    }),
                    timestamp: chrono::Utc::now(),
                }
            ],
        })
    }
    
    fn compare_values(&self, expected: &str, actual: &serde_json::Value, field: &str) -> (VerificationOutcome, f64, String) {
        // Extract the field from actual if it's an object
        let actual_value = if let Some(obj) = actual.as_object() {
            obj.get(field).cloned().unwrap_or(actual.clone())
        } else {
            actual.clone()
        };
        
        let actual_str = match &actual_value {
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Number(n) => n.to_string(),
            serde_json::Value::Bool(b) => b.to_string(),
            _ => actual_value.to_string(),
        };
        
        if actual_str == expected {
            (VerificationOutcome::Success, 1.0, format!("Exact match: {}", expected))
        } else if actual_str.contains(expected) || expected.contains(&actual_str) {
            (VerificationOutcome::Partial, 0.7, format!("Partial match: expected '{}', got '{}'", expected, actual_str))
        } else {
            (VerificationOutcome::Failure, 0.0, format!("Mismatch: expected '{}', got '{}'", expected, actual_str))
        }
    }
    
    async fn verify_webhook(&self, request: &VerificationRequest, events: &[String]) -> Result<VerificationResult> {
        let webhook_url = request.config.webhook_url.clone()
            .ok_or_else(|| anyhow::anyhow!("Webhook URL required for webhook verification"))?;
        
        let webhook_secret = request.config.webhook_secret.clone();
        
        // Register a channel to receive the webhook callback
        let (tx, rx) = oneshot::channel();
        let trace_id = request.trace_id.clone();
        
        self.pending_webhooks.write().await.insert(trace_id.clone(), tx);
        
        // In a real implementation, we'd have an HTTP server to receive webhooks
        // For now, we'll simulate by making a request to the webhook URL and waiting
        // The webhook should callback to our verification endpoint
        
        // Simulate waiting for webhook (in reality, this would be async)
        let timeout = Duration::from_secs(request.config.timeout_seconds);
        
        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(result)) => Ok(result),
            Ok(Err(_)) => {
                // Channel closed without sending
                Ok(VerificationResult {
                    outcome: VerificationOutcome::Failure,
                    confidence: 0.0,
                    insight: "Webhook channel closed unexpectedly".to_string(),
                    verified_at: chrono::Utc::now(),
                    method: request.config.method.clone(),
                    evidence: vec![],
                })
            }
            Err(_) => {
                // Timeout
                self.pending_webhooks.write().await.remove(&trace_id);
                Ok(VerificationResult {
                    outcome: VerificationOutcome::Failure,
                    confidence: 0.0,
                    insight: format!("Webhook verification timed out after {}s", request.config.timeout_seconds),
                    verified_at: chrono::Utc::now(),
                    method: request.config.method.clone(),
                    evidence: vec![],
                })
            }
        }
    }
    
    /// HMAC-SHA256 verify: body must match header `X-Webhook-Signature: sha256=<hex>` when `expected_secret` is Some.
    pub fn verify_webhook_signature(body: &[u8], signature_header: Option<&str>, expected_secret: Option<&str>) -> bool {
        let Some(secret) = expected_secret else { return true }; // no secret configured → skip
        let Some(hdr) = signature_header else { return false };
        let expected_hex = {
            use hmac::{Hmac, Mac};
            use sha2::Sha256;
            let mut mac = Hmac::<Sha256>::new_from_slice(secret.as_bytes()).expect("hmac key");
            mac.update(body);
            hex::encode(mac.finalize().into_bytes())
        };
        // header may be "sha256=<hex>" or bare hex
        let provided = hdr.strip_prefix("sha256=").unwrap_or(hdr).trim();
        // constant-time compare
        use subtle::ConstantTimeEq;
        expected_hex.as_bytes().ct_eq(provided.as_bytes()).unwrap_u8() == 1
    }

    pub async fn handle_webhook_callback(&self, trace_id: &str, payload: serde_json::Value) -> Result<()> {
        let mut pending = self.pending_webhooks.write().await;
        
        if let Some(tx) = pending.remove(trace_id) {
            // Parse webhook payload to determine outcome
            let outcome = self.parse_webhook_payload(&payload);
            
            let result = VerificationResult {
                outcome: outcome.0,
                confidence: outcome.1,
                insight: outcome.2,
                verified_at: chrono::Utc::now(),
                method: VerificationMethod::Webhook { events: vec![] },
                evidence: vec![
                    VerificationEvidence {
                        source: "webhook".to_string(),
                        data: payload,
                        timestamp: chrono::Utc::now(),
                    }
                ],
            };
            
            let _ = tx.send(result);
        }
        
        Ok(())
    }
    
    fn parse_webhook_payload(&self, payload: &serde_json::Value) -> (VerificationOutcome, f64, String) {
        // Parse based on common webhook formats (SendGrid, Stripe, etc.)
        if let Some(event) = payload.get("event").and_then(|e| e.as_str()) {
            match event {
                "delivered" | "sent" | "completed" | "success" => {
                    (VerificationOutcome::Success, 0.95, format!("Webhook event: {}", event))
                }
                "failed" | "bounced" | "blocked" | "error" => {
                    (VerificationOutcome::Failure, 0.95, format!("Webhook event: {}", event))
                }
                "opened" | "clicked" | "processed" => {
                    (VerificationOutcome::Partial, 0.8, format!("Webhook event: {}", event))
                }
                _ => {
                    (VerificationOutcome::Partial, 0.5, format!("Unknown webhook event: {}", event))
                }
            }
        } else if let Some(status) = payload.get("status").and_then(|s| s.as_str()) {
            match status {
                "success" | "completed" | "delivered" => {
                    (VerificationOutcome::Success, 0.9, format!("Status: {}", status))
                }
                "failed" | "error" => {
                    (VerificationOutcome::Failure, 0.9, format!("Status: {}", status))
                }
                _ => {
                    (VerificationOutcome::Partial, 0.5, format!("Status: {}", status))
                }
            }
        } else {
            (VerificationOutcome::Partial, 0.3, "Unable to parse webhook payload".to_string())
        }
    }
    
    async fn verify_human_review(&self, request: &VerificationRequest, required_approvers: u32) -> Result<VerificationResult> {
        // Create approval request via governance
        let approval_id = uuid::Uuid::new_v4().to_string();
        
        let (tx, rx) = oneshot::channel();
        self.pending_reviews.write().await.insert(approval_id.clone(), tx);
        
        // Notify approvers (would integrate with control plane notification system)
        self.notify_approvers(&approval_id, request, required_approvers).await?;
        
        // Wait for approval
        let timeout = Duration::from_secs(request.config.timeout_seconds);
        
        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(result)) => Ok(result),
            Ok(Err(_)) => Ok(VerificationResult {
                outcome: VerificationOutcome::Failure,
                confidence: 0.0,
                insight: "Approval channel closed".to_string(),
                verified_at: chrono::Utc::now(),
                method: request.config.method.clone(),
                evidence: vec![],
            }),
            Err(_) => {
                self.pending_reviews.write().await.remove(&approval_id);
                Ok(VerificationResult {
                    outcome: VerificationOutcome::Failure,
                    confidence: 0.0,
                    insight: format!("Human review timed out after {}s", request.config.timeout_seconds),
                    verified_at: chrono::Utc::now(),
                    method: request.config.method.clone(),
                    evidence: vec![],
                })
            }
        }
    }
    
    async fn notify_approvers(
        &self,
        approval_id: &str,
        request: &VerificationRequest,
        required_approvers: u32,
    ) -> Result<()> {
        // In production: send to control plane, email, Slack, etc.
        info!("Human review requested: {} (requires {} approvers)", approval_id, required_approvers);
        Ok(())
    }
    
    pub async fn handle_approval_callback(&self, approval_id: &str, approved: bool, reviewer: &str, modifications: Option<serde_json::Value>) -> Result<()> {
        let mut pending = self.pending_reviews.write().await;
        
        if let Some(tx) = pending.remove(approval_id) {
            let outcome = if approved {
                VerificationOutcome::Success
            } else {
                VerificationOutcome::Failure
            };
            
            let result = VerificationResult {
                outcome,
                confidence: if approved { 0.95 } else { 0.95 },
                insight: if approved {
                    format!("Approved by {}", reviewer)
                } else {
                    format!("Denied by {}", reviewer)
                },
                verified_at: chrono::Utc::now(),
                method: VerificationMethod::HumanReview { required_approvers: 1 },
                evidence: vec![
                    VerificationEvidence {
                        source: "human_review".to_string(),
                        data: serde_json::json!({
                            "approval_id": approval_id,
                            "approved": approved,
                            "reviewer": reviewer,
                            "modifications": modifications
                        }),
                        timestamp: chrono::Utc::now(),
                    }
                ],
            };
            
            let _ = tx.send(result);
        }
        
        Ok(())
    }
    
    async fn verify_custom(&self, request: &VerificationRequest, handler: &str) -> Result<VerificationResult> {
        // Custom verification handler - could be a WASM module or external service
        warn!("Custom verification handler not implemented: {}", handler);
        
        Ok(VerificationResult {
            outcome: VerificationOutcome::Partial,
            confidence: 0.1,
            insight: format!("Custom handler '{}' not implemented", handler),
            verified_at: chrono::Utc::now(),
            method: request.config.method.clone(),
            evidence: vec![],
        })
    }
}