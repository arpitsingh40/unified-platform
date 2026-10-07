"""
Core Python types for ARI SDK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator


# =============================================================================
# Enums
# =============================================================================

class AuthorityLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class VerificationMethod(str, Enum):
    READBACK = "readback"
    WEBHOOK = "webhook"
    HUMAN_REVIEW = "human_review"


class VerificationOutcome(str, Enum):
    SUCCESS = "Success"
    PARTIAL = "Partial"
    FAILED = "Failed"
    PENDING = "Pending"


class MemoryOpType(str, Enum):
    GET = "get"
    SET = "set"
    DELETE = "delete"
    EXISTS = "exists"
    LIST_KEYS = "list_keys"


# =============================================================================
# Agent Specification Types
# =============================================================================

class InputSpec(BaseModel):
    name: str
    type: str
    required: bool
    description: str


class OutputSpec(BaseModel):
    name: str
    type: str
    description: str


class GovernanceSpec(BaseModel):
    max_tool_calls: int = 20
    max_cost_usd: float = 1.0
    max_execution_time_ms: int = 300_000
    requires_approval_above_usd: float = 0.10

    @validator('max_tool_calls')
    def validate_max_tool_calls(cls, v):
        if v <= 0:
            raise ValueError('max_tool_calls must be > 0')
        return v

    @validator('max_cost_usd')
    def validate_max_cost_usd(cls, v):
        if v <= 0:
            raise ValueError('max_cost_usd must be > 0')
        return v

    @validator('max_execution_time_ms')
    def validate_max_execution_time_ms(cls, v):
        if v <= 0:
            raise ValueError('max_execution_time_ms must be > 0')
        return v


class MemorySpec(BaseModel):
    backend: str = "postgres"  # inmemory, redis, postgres
    ttl_days: int = 30


class AgentSpec(BaseModel):
    name: str
    version: str
    description: str = ""
    author: str = ""
    spec_version: str = "1.0"
    capabilities: List[str] = Field(default_factory=list)
    authority: AuthorityLevel = AuthorityLevel.L1
    schedule: str = "0 9 * * *"
    inputs: List[InputSpec] = Field(default_factory=list)
    outputs: List[OutputSpec] = Field(default_factory=list)
    governance: GovernanceSpec = Field(default_factory=GovernanceSpec)
    memory: MemorySpec = Field(default_factory=MemorySpec)

    @validator('capabilities')
    def validate_capabilities(cls, v):
        if not v:
            raise ValueError('at least one capability is required')
        return v

    @validator('authority')
    def validate_authority(cls, v):
        if v not in AuthorityLevel:
            raise ValueError(f'invalid authority: {v}')
        return v


# =============================================================================
# Runtime Types
# =============================================================================

class AgentInput(BaseModel):
    invocation_id: str
    agent_id: str
    org_id: str
    context: Dict[str, Any] = Field(default_factory=dict)
    trace_parent: Optional[str] = None


class AgentDecision(BaseModel):
    action: str
    reasoning: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    confidence: float = 0.8
    review_after_days: int = 1

    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence must be between 0.0 and 1.0')
        return v


class ToolCall(BaseModel):
    capability: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class ToolResult(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    cost_usd: float = 0.0


class AgentResult(BaseModel):
    success: bool
    decision: Optional[AgentDecision] = None
    error: Optional[str] = None


# =============================================================================
# Memory Types
# =============================================================================

class MemoryOp(BaseModel):
    op: MemoryOpType
    key: str
    value: Optional[Dict[str, Any]] = None
    ttl_seconds: Optional[int] = None


class MemoryResult(BaseModel):
    success: bool
    value: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# =============================================================================
# Verification Types
# =============================================================================

class VerificationRequest(BaseModel):
    capability: str
    tool: str
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    method: VerificationMethod


class VerificationResult(BaseModel):
    outcome: VerificationOutcome
    confidence: float
    insight: str

    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence must be between 0.0 and 1.0')
        return v


# =============================================================================
# Approval Types
# =============================================================================

class ApprovalRequest(BaseModel):
    invocation_id: str
    agent_id: str
    action: str
    risk_level: RiskLevel
    estimated_cost_usd: float
    context: Dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalResult(BaseModel):
    approved: bool
    approver: Optional[str] = None
    reason: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None


# =============================================================================
# Identity Types
# =============================================================================

class AgentIdentity(BaseModel):
    agent_id: str
    org_id: str
    capabilities: List[str] = Field(default_factory=list)
    authority: AuthorityLevel
    certificate_pem: str
    public_key: str


# =============================================================================
# Invocation Types
# =============================================================================

class InvocationRequest(BaseModel):
    invocation_id: str
    agent_id: str
    org_id: str
    context: Dict[str, Any] = Field(default_factory=dict)
    trace_parent: Optional[str] = None


class ToolExecution(BaseModel):
    capability: str
    tool: str
    args: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    cost_usd: float = 0.0
    verified: bool = False


class InvocationResult(BaseModel):
    invocation_id: str
    agent_id: str
    success: bool
    decision: Optional[AgentDecision] = None
    executions: List[ToolExecution] = Field(default_factory=list)
    verification: List[VerificationResult] = Field(default_factory=list)
    total_time_ms: int = 0
    total_cost_usd: float = 0.0
    error: Optional[str] = None


# =============================================================================
# Registry Types
# =============================================================================

class RegistryManifest(BaseModel):
    name: str
    version: str
    description: str
    author: str
    component_hash: str
    component_size: int
    capabilities: List[str] = Field(default_factory=list)
    authority: AuthorityLevel
    spec_version: str
    created_at: datetime
    signature: Optional[str] = None


# =============================================================================
# Deployment Types
# =============================================================================

class ResourceRequirements(BaseModel):
    cpu_millicores: int = 500
    memory_mb: int = 512
    max_execution_time_ms: int = 300_000


class DeploymentRequest(BaseModel):
    agent_name: str
    agent_version: str
    environment: str
    replicas: int = 1
    auto_scale: bool = False
    resources: ResourceRequirements = Field(default_factory=ResourceRequirements)
    secrets: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)


class DeploymentResponse(BaseModel):
    deployment_id: str
    status: str
    endpoint: Optional[str] = None
    created_at: datetime


# =============================================================================
# Error Types
# =============================================================================

class AriError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(AriError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", 400, details)


class NotFoundError(AriError):
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)


class AuthorizationError(AriError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, "UNAUTHORIZED", 401)


class RuntimeError(AriError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "RUNTIME_ERROR", 500, details)