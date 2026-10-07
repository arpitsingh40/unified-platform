/**
 * Core TypeScript types for ARI SDK
 */

// ============================================================================
// Agent Specification Types
// ============================================================================

export interface AgentSpec {
  name: string;
  version: string;
  description: string;
  author: string;
  spec_version: string;
  capabilities: string[];
  authority: AuthorityLevel;
  schedule: string;
  inputs: InputSpec[];
  outputs: OutputSpec[];
  governance: GovernanceSpec;
  memory: MemorySpec;
}

export type AuthorityLevel = 'L1' | 'L2' | 'L3' | 'L4' | 'L5';

export interface InputSpec {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

export interface OutputSpec {
  name: string;
  type: string;
  description: string;
}

export interface GovernanceSpec {
  max_tool_calls: number;
  max_cost_usd: number;
  max_execution_time_ms: number;
  requires_approval_above_usd: number;
}

export interface MemorySpec {
  backend: 'inmemory' | 'redis' | 'postgres';
  ttl_days: number;
}

// ============================================================================
// Runtime Types
// ============================================================================

export interface AgentInput {
  invocation_id: string;
  agent_id: string;
  org_id: string;
  context: Record<string, unknown>;
  trace_parent?: string;
}

export interface AgentResult {
  success: boolean;
  decision?: AgentDecision;
  error?: string;
}

export interface AgentDecision {
  action: string;
  reasoning: string;
  tool_calls: ToolCall[];
  confidence: number;
  review_after_days: number;
}

export interface ToolCall {
  capability: string;
  tool: string;
  args: Record<string, unknown>;
  reason: string;
}

export interface ToolResult {
  success: boolean;
  result?: Record<string, unknown>;
  error?: string;
  execution_time_ms: number;
  cost_usd: number;
}

// ============================================================================
// Memory Types
// ============================================================================

export type MemoryOpType = 'get' | 'set' | 'delete' | 'exists' | 'list_keys';

export interface MemoryOp {
  op: MemoryOpType;
  key: string;
  value?: Record<string, unknown>;
  ttl_seconds?: number;
}

export interface MemoryResult {
  success: boolean;
  value?: Record<string, unknown>;
  error?: string;
}

// ============================================================================
// Verification Types
// ============================================================================

export type VerificationMethod = 'readback' | 'webhook' | 'human_review';

export interface VerificationRequest {
  capability: string;
  tool: string;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  method: VerificationMethod;
}

export type VerificationOutcome = 'Success' | 'Partial' | 'Failed' | 'Pending';

export interface VerificationResult {
  outcome: VerificationOutcome;
  confidence: number;
  insight: string;
}

// ============================================================================
// Approval Types
// ============================================================================

export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Critical';

export interface ApprovalRequest {
  invocation_id: string;
  agent_id: string;
  action: string;
  risk_level: RiskLevel;
  estimated_cost_usd: number;
  context: Record<string, unknown>;
  requested_at: string;
}

export interface ApprovalResult {
  approved: boolean;
  approver?: string;
  reason?: string;
  conditions: string[];
  expires_at?: string;
}

// ============================================================================
// Identity Types
// ============================================================================

export interface AgentIdentity {
  agent_id: string;
  org_id: string;
  capabilities: string[];
  authority: AuthorityLevel;
  certificate_pem: string;
  public_key: string;
}

// ============================================================================
// Invocation Types
// ============================================================================

export interface InvocationRequest {
  invocation_id: string;
  agent_id: string;
  org_id: string;
  context: Record<string, unknown>;
  trace_parent?: string;
}

export interface InvocationResult {
  invocation_id: string;
  agent_id: string;
  success: boolean;
  decision?: AgentDecision;
  executions: ToolExecution[];
  verification: VerificationResult[];
  total_time_ms: number;
  total_cost_usd: number;
  error?: string;
}

export interface ToolExecution {
  capability: string;
  tool: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  execution_time_ms: number;
  cost_usd: number;
  verified: boolean;
}

// ============================================================================
// Registry Types
// ============================================================================

export interface RegistryManifest {
  name: string;
  version: string;
  description: string;
  author: string;
  component_hash: string;
  component_size: number;
  capabilities: string[];
  authority: AuthorityLevel;
  spec_version: string;
  created_at: string;
  signature?: string;
}

// ============================================================================
// Deployment Types
// ============================================================================

export interface DeploymentRequest {
  agent_name: string;
  agent_version: string;
  environment: string;
  replicas: number;
  auto_scale: boolean;
  resources: ResourceRequirements;
  secrets: string[];
  config: Record<string, unknown>;
}

export interface ResourceRequirements {
  cpu_millicores: number;
  memory_mb: number;
  max_execution_time_ms: number;
}

export interface DeploymentResponse {
  deployment_id: string;
  status: string;
  endpoint?: string;
  created_at: string;
}

// ============================================================================
// Error Types
// ============================================================================

export class AriError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode?: number,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'AriError';
  }
}

export class ValidationError extends AriError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'VALIDATION_ERROR', 400, details);
    this.name = 'ValidationError';
  }
}

export class NotFoundError extends AriError {
  constructor(resource: string) {
    super(`${resource} not found`, 'NOT_FOUND', 404);
    this.name = 'NotFoundError';
  }
}

export class AuthorizationError extends AriError {
  constructor(message: string = 'Unauthorized') {
    super(message, 'UNAUTHORIZED', 401);
    this.name = 'AuthorizationError';
  }
}

export class RuntimeError extends AriError {
  constructor(message: string, details?: Record<string, unknown>) {
    super(message, 'RUNTIME_ERROR', 500, details);
    this.name = 'RuntimeError';
  }
}

// ============================================================================
// Configuration Types
// ============================================================================

export interface RuntimeConfig {
  server: ServerConfig;
  runtime: RuntimeEngineConfig;
  governance: GovernanceConfig;
  capabilities: CapabilitiesConfig;
  memory: MemoryConfig;
  telemetry: TelemetryConfig;
  storage: StorageConfig;
  identity: IdentityConfig;
}

export interface ServerConfig {
  host: string;
  port: number;
  control_plane_url?: string;
  tls_cert?: string;
  tls_key?: string;
}

export interface RuntimeEngineConfig {
  wasm_cache_dir: string;
  max_concurrent_agents: number;
  default_execution_timeout_ms: number;
  default_memory_limit_mb: number;
  fuel_limit?: number;
  epoch_interruption: boolean;
}

export interface GovernanceConfig {
  kill_switch_enabled: boolean;
  dry_run_default: boolean;
  default_weekly_cap_usd: number;
  governance_state_db: string;
  org_governance_db: string;
}

export interface CapabilitiesConfig {
  registry_url: string;
  builtin_capabilities: string[];
  capability_timeout_ms: number;
  max_retries: number;
  retry_base_delay_ms: number;
}

export interface MemoryConfig {
  backend: 'inmemory' | 'redis' | 'postgres';
  redis_url?: string;
  postgres_url?: string;
  encryption_key?: string;
  ttl_seconds?: number;
}

export interface TelemetryConfig {
  tracing_level: string;
  otel_endpoint?: string;
  metrics_port: number;
  log_json: boolean;
}

export interface StorageConfig {
  postgres_url: string;
  pool_size: number;
  migration_dir: string;
}

export interface IdentityConfig {
  ca_cert: string;
  ca_key: string;
  cert_ttl_days: number;
  key_algorithm: string;
}