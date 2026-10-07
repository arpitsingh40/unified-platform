//! Capability registry and execution engine

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use tracing::{debug, info, warn, error};
use uuid::Uuid;

use crate::config::CapabilitiesConfig;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Capability {
    pub id: String,
    pub name: String,
    pub description: String,
    pub tools: Vec<Tool>,
    pub governance: GovernanceConfig,
    pub provider: CapabilityProvider,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    pub id: String,
    pub name: String,
    pub description: String,
    pub input_schema: serde_json::Value,
    pub output_schema: serde_json::Value,
    pub cost_usd_estimate: f64,
    pub latency_estimate_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceConfig {
    pub max_per_day: Option<u32>,
    pub max_cost_usd: Option<f64>,
    pub requires_approval: bool,
    pub template_required: bool,
    pub allowed_tools: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum CapabilityProvider {
    Builtin { module: String },
    Http { 
        base_url: String,
        auth: HttpAuth,
        timeout_ms: u64,
    },
    Composio { 
        api_key: String,
        toolkit: String,
    },
    Mcp { 
        server_url: String,
        transport: McpTransport,
    },
    Custom { 
        factory: String,
        config: serde_json::Value,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum HttpAuth {
    None,
    Bearer { token: String },
    ApiKey { header: String, value: String },
    Basic { username: String, password: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum McpTransport {
    Stdio { command: String, args: Vec<String> },
    Http { url: String },
    WebSocket { url: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityRequest {
    pub capability: String,
    pub tool: String,
    pub args: serde_json::Value,
    pub reason: String,
    pub trace_id: String,
    pub idempotency_key: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityResponse {
    pub success: bool,
    pub result: Option<serde_json::Value>,
    pub error: Option<String>,
    pub execution_time_ms: u64,
    pub cost_usd: f64,
    pub verification_status: VerificationStatus,
    pub provider_response: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "status")]
pub enum VerificationStatus {
    Pending,
    Verified { outcome: VerificationOutcome, confidence: f64, insight: String },
    Failed { reason: String },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum VerificationOutcome {
    Success,
    Partial,
    Failure,
}

pub struct CapabilityRegistry {
    config: CapabilitiesConfig,
    capabilities: Arc<RwLock<HashMap<String, Capability>>>,
    http_client: reqwest::Client,
    usage_tracker: Arc<RwLock<UsageTracker>>,
}

#[derive(Debug, Default)]
struct UsageTracker {
    daily_counts: HashMap<String, u32>, // capability_id -> count
    daily_costs: HashMap<String, f64>,  // capability_id -> cost
    last_reset: chrono::DateTime<chrono::Utc>,
}

impl CapabilityRegistry {
    pub fn new(config: CapabilitiesConfig) -> Result<Self> {
        let http_client = reqwest::Client::builder()
            .timeout(Duration::from_millis(config.capability_timeout_ms))
            .build()?;
        
        let registry = Self {
            config,
            capabilities: Arc::new(RwLock::new(HashMap::new())),
            http_client,
            usage_tracker: Arc::new(RwLock::new(UsageTracker::default())),
        };
        
        Ok(registry)
    }
    
    pub async fn register(&self, capability: Capability) -> Result<()> {
        let mut caps = self.capabilities.write().await;
        caps.insert(capability.id.clone(), capability);
        Ok(())
    }
    
    pub async fn register_builtin(&self) -> Result<()> {
        // HTTP capability
        self.register(Capability {
            id: "http".to_string(),
            name: "HTTP Requests".to_string(),
            description: "Make arbitrary HTTP requests".to_string(),
            tools: vec![
                Tool {
                    id: "http.get".to_string(),
                    name: "GET Request".to_string(),
                    description: "Make a GET request".to_string(),
                    input_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "headers": {"type": "object"},
                            "query": {"type": "object"}
                        },
                        "required": ["url"]
                    }),
                    output_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "status": {"type": "integer"},
                            "body": {"type": "string"},
                            "headers": {"type": "object"}
                        }
                    }),
                    cost_usd_estimate: 0.0001,
                    latency_estimate_ms: 500,
                },
                Tool {
                    id: "http.post".to_string(),
                    name: "POST Request".to_string(),
                    description: "Make a POST request with JSON body".to_string(),
                    input_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "headers": {"type": "object"},
                            "body": {"type": "object"}
                        },
                        "required": ["url"]
                    }),
                    output_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "status": {"type": "integer"},
                            "body": {"type": "string"},
                            "headers": {"type": "object"}
                        }
                    }),
                    cost_usd_estimate: 0.0001,
                    latency_estimate_ms: 500,
                },
            ],
            governance: GovernanceConfig {
                max_per_day: Some(10000),
                max_cost_usd: Some(10.0),
                requires_approval: false,
                template_required: false,
                allowed_tools: vec!["http.get".to_string(), "http.post".to_string()],
            },
            provider: CapabilityProvider::Builtin { module: "http".to_string() },
        }).await?;
        
        // Email capability (via provider)
        self.register(Capability {
            id: "email".to_string(),
            name: "Email".to_string(),
            description: "Send emails via multiple providers".to_string(),
            tools: vec![
                Tool {
                    id: "email.send".to_string(),
                    name: "Send Email".to_string(),
                    description: "Send an email".to_string(),
                    input_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "to": {"type": "array", "items": {"type": "string"}},
                            "cc": {"type": "array", "items": {"type": "string"}},
                            "bcc": {"type": "array", "items": {"type": "string"}},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "body_html": {"type": "string"},
                            "attachments": {"type": "array"}
                        },
                        "required": ["to", "subject", "body"]
                    }),
                    output_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "message_id": {"type": "string"},
                            "status": {"type": "string"}
                        }
                    }),
                    cost_usd_estimate: 0.001,
                    latency_estimate_ms: 2000,
                },
            ],
            governance: GovernanceConfig {
                max_per_day: Some(500),
                max_cost_usd: Some(5.0),
                requires_approval: true,
                template_required: true,
                allowed_tools: vec!["email.send".to_string()],
            },
            provider: CapabilityProvider::Http {
                base_url: "https://api.sendgrid.com/v3".to_string(),
                auth: HttpAuth::Bearer { token: "${SENDGRID_API_KEY}".to_string() },
                timeout_ms: 30000,
            },
        }).await?;
        
        // CRM capability (Composio)
        self.register(Capability {
            id: "crm".to_string(),
            name: "CRM Operations".to_string(),
            description: "CRUD operations on CRM records via Composio".to_string(),
            tools: vec![
                Tool {
                    id: "crm.query".to_string(),
                    name: "Query CRM".to_string(),
                    description: "Query CRM for records".to_string(),
                    input_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "object": {"type": "string"},
                            "filter": {"type": "object"},
                            "fields": {"type": "array", "items": {"type": "string"}},
                            "limit": {"type": "integer"}
                        },
                        "required": ["object"]
                    }),
                    output_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "records": {"type": "array"},
                            "total": {"type": "integer"}
                        }
                    }),
                    cost_usd_estimate: 0.001,
                    latency_estimate_ms: 3000,
                },
                Tool {
                    id: "crm.upsert".to_string(),
                    name: "Upsert CRM Record".to_string(),
                    description: "Create or update a CRM record".to_string(),
                    input_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "object": {"type": "string"},
                            "data": {"type": "object"},
                            "id_field": {"type": "string"}
                        },
                        "required": ["object", "data"]
                    }),
                    output_schema: serde_json::json!({
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "created": {"type": "boolean"}
                        }
                    }),
                    cost_usd_estimate: 0.001,
                    latency_estimate_ms: 3000,
                },
            ],
            governance: GovernanceConfig {
                max_per_day: Some(1000),
                max_cost_usd: Some(10.0),
                requires_approval: true,
                template_required: false,
                allowed_tools: vec!["crm.query".to_string(), "crm.upsert".to_string()],
            },
            provider: CapabilityProvider::Composio {
                api_key: "${COMPOSIO_API_KEY}".to_string(),
                toolkit: "SALESFORCE".to_string(),
            },
        }).await?;
        
        info!("Registered {} builtin capabilities", self.capabilities.read().await.len());
        Ok(())
    }
    
    pub async fn execute(&self, request: CapabilityRequest) -> Result<CapabilityResponse> {
        let start = Instant::now();
        
        // Get capability
        let caps = self.capabilities.read().await;
        let capability = caps.get(&request.capability)
            .ok_or_else(|| anyhow::anyhow!("Capability not found: {}", request.capability))?
            .clone();
        drop(caps);
        
        // Get tool
        let tool = capability.tools.iter()
            .find(|t| t.id == request.tool)
            .ok_or_else(|| anyhow::anyhow!("Tool not found: {} in capability {}", request.tool, request.capability))?;
        
        // Check governance
        self.check_governance(&capability, tool, &request).await?;
        
        // Execute with retries
        let mut last_error = None;
        for attempt in 0..=self.config.max_retries {
            match self.execute_once(&capability, tool, &request).await {
                Ok(mut response) => {
                    response.execution_time_ms = start.elapsed().as_millis() as u64;
                    
                    // Track usage
                    self.track_usage(&capability.id, &response).await;
                    
                    return Ok(response);
                }
                Err(e) => {
                    last_error = Some(e);
                    if attempt < self.config.max_retries {
                        let delay = Duration::from_millis(
                            self.config.retry_base_delay_ms * (2_u64.pow(attempt as u32))
                        );
                        warn!("Capability execution failed (attempt {}/{}): {}. Retrying in {:?}", 
                            attempt + 1, self.config.max_retries + 1, last_error.as_ref().unwrap(), delay);
                        tokio::time::sleep(delay).await;
                    }
                }
            }
        }
        
        Err(last_error.unwrap_or_else(|| anyhow::anyhow!("Execution failed after retries")))
    }
    
    async fn check_governance(
        &self,
        capability: &Capability,
        tool: &Tool,
        request: &CapabilityRequest,
    ) -> Result<()> {
        let mut usage = self.usage_tracker.write().await;
        
        // Reset daily counters if needed
        let now = chrono::Utc::now();
        if now.date_naive() != usage.last_reset.date_naive() {
            usage.daily_counts.clear();
            usage.daily_costs.clear();
            usage.last_reset = now;
        }
        
        // Check daily limit
        if let Some(max_per_day) = capability.governance.max_per_day {
            let count = usage.daily_counts.get(&capability.id).copied().unwrap_or(0);
            if count >= max_per_day {
                return Err(anyhow::anyhow!("Daily limit exceeded for capability: {}", capability.id));
            }
        }
        
        // Check daily cost
        if let Some(max_cost) = capability.governance.max_cost_usd {
            let cost = usage.daily_costs.get(&capability.id).copied().unwrap_or(0.0);
            if cost + tool.cost_usd_estimate > max_cost {
                return Err(anyhow::anyhow!("Daily cost limit exceeded for capability: {}", capability.id));
            }
        }
        
        Ok(())
    }
    
    async fn execute_once(
        &self,
        capability: &Capability,
        tool: &Tool,
        request: &CapabilityRequest,
    ) -> Result<CapabilityResponse> {
        match &capability.provider {
            CapabilityProvider::Builtin { module } => {
                self.execute_builtin(module, tool, &request.args).await
            }
            CapabilityProvider::Http { base_url, auth, timeout_ms } => {
                self.execute_http(base_url, auth, tool, &request.args, *timeout_ms).await
            }
            CapabilityProvider::Composio { api_key, toolkit } => {
                self.execute_composio(api_key, toolkit, tool, &request.args).await
            }
            CapabilityProvider::Mcp { server_url, transport } => {
                self.execute_mcp(server_url, transport, tool, &request.args).await
            }
            CapabilityProvider::Custom { factory, config } => {
                self.execute_custom(factory, config, tool, &request.args).await
            }
        }
    }
    
    async fn execute_builtin(
        &self,
        module: &str,
        tool: &Tool,
        args: &serde_json::Value,
    ) -> Result<CapabilityResponse> {
        match module {
            "http" => {
                let url = args["url"].as_str().ok_or_else(|| anyhow::anyhow!("Missing url"))?;
                let method = tool.id.split('.').nth(1).unwrap_or("get");
                
                let mut req = match method {
                    "get" => self.http_client.get(url),
                    "post" => self.http_client.post(url),
                    _ => return Err(anyhow::anyhow!("Unsupported HTTP method: {}", method)),
                };
                
                if let Some(headers) = args.get("headers").and_then(|h| h.as_object()) {
                    for (k, v) in headers {
                        req = req.header(k, v.as_str().unwrap_or(""));
                    }
                }
                
                if method == "post" {
                    if let Some(body) = args.get("body") {
                        req = req.json(body);
                    }
                } else if let Some(query) = args.get("query").and_then(|q| q.as_object()) {
                    req = req.query(&query);
                }
                
                let resp = req.send().await?;
                let status = resp.status().as_u16();
                let headers: HashMap<String, String> = resp.headers()
                    .iter()
                    .map(|(k, v)| (k.to_string(), v.to_str().unwrap_or("").to_string()))
                    .collect();
                let body = resp.text().await?;
                
                Ok(CapabilityResponse {
                    success: status < 400,
                    result: Some(serde_json::json!({ "status": status, "body": body, "headers": headers })),
                    error: if status >= 400 { Some(format!("HTTP {}", status)) } else { None },
                    execution_time_ms: 0, // filled by caller
                    cost_usd: tool.cost_usd_estimate,
                    verification_status: VerificationStatus::Pending,
                    provider_response: None,
                })
            }
            _ => Err(anyhow::anyhow!("Unknown builtin module: {}", module)),
        }
    }
    
    async fn execute_http(
        &self,
        base_url: &str,
        auth: &HttpAuth,
        tool: &Tool,
        args: &serde_json::Value,
        timeout_ms: u64,
    ) -> Result<CapabilityResponse> {
        let url = format!("{}/{}", base_url.trim_end_matches('/'), tool.id);
        
        let mut req = self.http_client.post(&url).timeout(Duration::from_millis(timeout_ms));
        
        match auth {
            HttpAuth::Bearer { token } => {
                req = req.bearer_auth(token);
            }
            HttpAuth::ApiKey { header, value } => {
                req = req.header(header, value);
            }
            HttpAuth::Basic { username, password } => {
                req = req.basic_auth(username, Some(password));
            }
            HttpAuth::None => {}
        }
        
        req = req.json(args);
        
        let resp = req.send().await?;
        let status = resp.status().as_u16();
        let body: serde_json::Value = resp.json().await?;
        
        Ok(CapabilityResponse {
            success: status < 400,
            result: Some(body),
            error: if status >= 400 { Some(format!("HTTP {}", status)) } else { None },
            execution_time_ms: 0,
            cost_usd: tool.cost_usd_estimate,
            verification_status: VerificationStatus::Pending,
            provider_response: None,
        })
    }
    
    async fn execute_composio(
        &self,
        api_key: &str,
        toolkit: &str,
        tool: &Tool,
        args: &serde_json::Value,
    ) -> Result<CapabilityResponse> {
        // Composio API call
        let url = "https://backend.composio.dev/api/v1/tools/execute";
        
        let payload = serde_json::json!({
            "toolkit": toolkit,
            "tool": tool.id,
            "arguments": args,
        });
        
        let resp = self.http_client
            .post(url)
            .bearer_auth(api_key)
            .json(&payload)
            .send()
            .await?;
        
        let status = resp.status().as_u16();
        let body: serde_json::Value = resp.json().await?;
        
        Ok(CapabilityResponse {
            success: status < 400,
            result: Some(body.clone()),
            error: if status >= 400 { Some(format!("Composio HTTP {}", status)) } else { None },
            execution_time_ms: 0,
            cost_usd: tool.cost_usd_estimate,
            verification_status: VerificationStatus::Pending,
            provider_response: Some(body),
        })
    }
    
    async fn execute_mcp(
        &self,
        _server_url: &str,
        _transport: &McpTransport,
        _tool: &Tool,
        _args: &serde_json::Value,
    ) -> Result<CapabilityResponse> {
        // TODO: Implement MCP client
        Err(anyhow::anyhow!("MCP execution not yet implemented"))
    }
    
    async fn execute_custom(
        &self,
        _factory: &str,
        _config: &serde_json::Value,
        _tool: &Tool,
        _args: &serde_json::Value,
    ) -> Result<CapabilityResponse> {
        Err(anyhow::anyhow!("Custom capability execution not yet implemented"))
    }
    
    async fn track_usage(&self, capability_id: &str, response: &CapabilityResponse) {
        let mut usage = self.usage_tracker.write().await;
        *usage.daily_counts.entry(capability_id.to_string()).or_insert(0) += 1;
        *usage.daily_costs.entry(capability_id.to_string()).or_insert(0.0) += response.cost_usd;
    }
    
    pub async fn get_capability(&self, id: &str) -> Option<Capability> {
        self.capabilities.read().await.get(id).cloned()
    }
    
    pub async fn list_capabilities(&self) -> Vec<Capability> {
        self.capabilities.read().await.values().cloned().collect()
    }
}