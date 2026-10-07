//! ARI Guest SDK - Types and host functions for agents running in the ARI runtime

use serde::{Deserialize, Serialize};
use serde_json::Value;
use anyhow::Result;

/// Input provided to an agent at invocation time
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInput {
    /// Unique invocation identifier
    pub invocation_id: String,
    /// Agent identifier
    pub agent_id: String,
    /// Organization identifier
    pub org_id: String,
    /// Execution context from the scheduler/trigger
    pub context: Value,
    /// Distributed tracing parent
    pub trace_parent: Option<String>,
}

/// Result returned by an agent after execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    /// Whether execution was successful
    pub success: bool,
    /// The agent's decision (if successful)
    pub decision: Option<AgentDecision>,
    /// Error message (if failed)
    pub error: Option<String>,
}

/// A decision made by the agent, including tool calls to execute
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDecision {
    /// High-level action name (e.g., "ANALYZE", "NOTIFY", "UPDATE")
    pub action: String,
    /// Human-readable reasoning for the decision
    pub reasoning: String,
    /// Tool calls to execute
    pub tool_calls: Vec<ToolCall>,
    /// Confidence in this decision (0.0 - 1.0)
    pub confidence: f64,
    /// Days after which this decision should be reviewed
    pub review_after_days: u32,
}

/// A single tool call to be executed by the runtime
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCall {
    /// Capability namespace (e.g., "crm", "email", "http")
    pub capability: String,
    /// Specific tool within the capability (e.g., "crm.query", "email.send")
    pub tool: String,
    /// Arguments for the tool call
    pub args: Value,
    /// Reason for this tool call (for audit/logging)
    pub reason: String,
}

/// Result of a single tool execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    /// Whether the tool call succeeded
    pub success: bool,
    /// Result data (if successful)
    pub result: Option<Value>,
    /// Error message (if failed)
    pub error: Option<String>,
    /// Execution time in milliseconds
    pub execution_time_ms: u64,
    /// Cost in USD
    pub cost_usd: f64,
}

/// Memory operations for persistent agent state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryOp {
    /// Operation type
    pub op: MemoryOpType,
    /// Key
    pub key: String,
    /// Value (for set operations)
    pub value: Option<Value>,
    /// TTL in seconds (optional)
    pub ttl_seconds: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MemoryOpType {
    Get,
    Set,
    Delete,
    Exists,
    ListKeys,
}

/// Result of a memory operation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryResult {
    pub success: bool,
    pub value: Option<Value>,
    pub error: Option<String>,
}

/// Verification request for outcome verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationRequest {
    pub capability: String,
    pub tool: String,
    pub expected: Value,
    pub actual: Value,
    pub method: VerificationMethod,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum VerificationMethod {
    Readback,
    Webhook,
    HumanReview,
}

/// Verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationResult {
    pub outcome: VerificationOutcome,
    pub confidence: f64,
    pub insight: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum VerificationOutcome {
    Success,
    Partial,
    Failed,
    Pending,
}

/// Approval request for high-risk actions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalRequest {
    pub invocation_id: String,
    pub agent_id: String,
    pub action: String,
    pub risk_level: RiskLevel,
    pub estimated_cost_usd: f64,
    pub context: Value,
    pub requested_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

/// Approval result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovalResult {
    pub approved: bool,
    pub approver: Option<String>,
    pub reason: Option<String>,
    pub conditions: Vec<String>,
    pub expires_at: Option<String>,
}

/// Host functions available to guest components
#[link(wasm_import_module = "ari:host")]
unsafe extern "C" {
    /// Execute a tool call
    fn tool_call(
        capability_ptr: *const u8, capability_len: usize,
        tool_ptr: *const u8, tool_len: usize,
        args_ptr: *const u8, args_len: usize,
        reason_ptr: *const u8, reason_len: usize,
        result_ptr: *mut u8, result_len: usize,
        result_written: *mut usize
    ) -> i32;

    /// Memory operations
    fn memory_op(
        op_ptr: *const u8, op_len: usize,
        result_ptr: *mut u8, result_len: usize,
        result_written: *mut usize
    ) -> i32;

    /// Request verification
    fn verify(
        request_ptr: *const u8, request_len: usize,
        result_ptr: *mut u8, result_len: usize,
        result_written: *mut usize
    ) -> i32;

    /// Request approval
    fn approve(
        request_ptr: *const u8, request_len: usize,
        result_ptr: *mut u8, result_len: usize,
        result_written: *mut usize
    ) -> i32;

    /// Log a message
    fn log(
        level_ptr: *const u8, level_len: usize,
        message_ptr: *const u8, message_len: usize
    ) -> i32;

    /// Get current timestamp
    fn timestamp() -> u64;

    /// Get agent identity
    fn identity(
        result_ptr: *mut u8, result_len: usize,
        result_written: *mut usize
    ) -> i32;
}

/// High-level wrapper for host functions
pub struct Host;

impl Host {
    /// Call a capability tool
    pub fn tool_call(capability: &str, tool: &str, args: &Value, reason: &str) -> Result<ToolResult> {
        let request = serde_json::json!({
            "capability": capability,
            "tool": tool,
            "args": args,
            "reason": reason,
        });
        
        let request_bytes = serde_json::to_vec(&request)?;
        let mut result_buf = vec![0u8; 65536];
        let mut written = 0usize;
        
        let ret = unsafe {
            tool_call(
                capability.as_ptr(), capability.len(),
                tool.as_ptr(), tool.len(),
                request_bytes.as_ptr(), request_bytes.len(),
                reason.as_ptr(), reason.len(),
                result_buf.as_mut_ptr(), result_buf.len(),
                &mut written,
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Host call failed with code: {}", ret));
        }
        
        let result_bytes = &result_buf[..written];
        let result: ToolResult = serde_json::from_slice(result_bytes)?;
        Ok(result)
    }
    
    /// Perform a memory operation
    pub fn memory_op(op: MemoryOp) -> Result<MemoryResult> {
        let op_bytes = serde_json::to_vec(&op)?;
        let mut result_buf = vec![0u8; 65536];
        let mut written = 0usize;
        
        let ret = unsafe {
            memory_op(
                op_bytes.as_ptr(), op_bytes.len(),
                result_buf.as_mut_ptr(), result_buf.len(),
                &mut written,
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Memory op failed with code: {}", ret));
        }
        
        let result_bytes = &result_buf[..written];
        let result: MemoryResult = serde_json::from_slice(result_bytes)?;
        Ok(result)
    }
    
    /// Request verification of a tool result
    pub fn verify(request: VerificationRequest) -> Result<VerificationResult> {
        let request_bytes = serde_json::to_vec(&request)?;
        let mut result_buf = vec![0u8; 65536];
        let mut written = 0usize;
        
        let ret = unsafe {
            verify(
                request_bytes.as_ptr(), request_bytes.len(),
                result_buf.as_mut_ptr(), result_buf.len(),
                &mut written,
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Verify failed with code: {}", ret));
        }
        
        let result_bytes = &result_buf[..written];
        let result: VerificationResult = serde_json::from_slice(result_bytes)?;
        Ok(result)
    }
    
    /// Request approval for a high-risk action
    pub fn approve(request: ApprovalRequest) -> Result<ApprovalResult> {
        let request_bytes = serde_json::to_vec(&request)?;
        let mut result_buf = vec![0u8; 65536];
        let mut written = 0usize;
        
        let ret = unsafe {
            approve(
                request_bytes.as_ptr(), request_bytes.len(),
                result_buf.as_mut_ptr(), result_buf.len(),
                &mut written,
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Approve failed with code: {}", ret));
        }
        
        let result_bytes = &result_buf[..written];
        let result: ApprovalResult = serde_json::from_slice(result_bytes)?;
        Ok(result)
    }
    
    /// Log a message
    pub fn log(level: &str, message: &str) -> Result<()> {
        let ret = unsafe {
            log(
                level.as_ptr(), level.len(),
                message.as_ptr(), message.len(),
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Log failed with code: {}", ret));
        }
        
        Ok(())
    }
    
    /// Get current Unix timestamp in milliseconds
    pub fn timestamp() -> u64 {
        unsafe { timestamp() }
    }
    
    /// Get agent identity
    pub fn identity() -> Result<AgentIdentity> {
        let mut result_buf = vec![0u8; 65536];
        let mut written = 0usize;
        
        let ret = unsafe {
            identity(
                result_buf.as_mut_ptr(), result_buf.len(),
                &mut written,
            )
        };
        
        if ret != 0 {
            return Err(anyhow::anyhow!("Identity failed with code: {}", ret));
        }
        
        let result_bytes = &result_buf[..written];
        let identity: AgentIdentity = serde_json::from_slice(result_bytes)?;
        Ok(identity)
    }
}

/// Agent identity information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentIdentity {
    pub agent_id: String,
    pub org_id: String,
    pub capabilities: Vec<String>,
    pub authority: String,
    pub certificate_pem: String,
    pub public_key: String,
}

/// Entry point for agents - implement this in your agent
pub fn run(input: AgentInput) -> AgentResult {
    // This is the default implementation - agents should override this
    AgentResult {
        success: false,
        decision: None,
        error: Some("Agent must implement run() function".to_string()),
    }
}

// Re-export for convenience
pub use serde_json::json;