"""
ARI Python SDK

A trillion-dollar platform for running autonomous agents with:
- WASM-based isolation
- Capability registry with governance
- Built-in verification & approval workflows
- Cryptographic identity & signing
"""

from .client import AriClient, create_client
from .spec import AgentSpec, SpecBuilder, create_agent_spec, validate_spec
from .types import (
    AgentInput,
    AgentResult,
    AgentDecision,
    ToolCall,
    ToolResult,
    InvocationRequest,
    InvocationResult,
    ToolExecution,
    VerificationRequest,
    VerificationResult,
    ApprovalRequest,
    ApprovalResult,
    AgentIdentity,
    RegistryManifest,
    DeploymentRequest,
    DeploymentResponse,
    ResourceRequirements,
    AuthorityLevel,
    RiskLevel,
    VerificationMethod,
    VerificationOutcome,
    MemoryOp,
    MemoryOpType,
    MemoryResult,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "AriClient",
    "create_client",
    # Spec
    "AgentSpec",
    "SpecBuilder",
    "create_agent_spec",
    "validate_spec",
    # Types
    "AgentInput",
    "AgentResult",
    "AgentDecision",
    "ToolCall",
    "ToolResult",
    "InvocationRequest",
    "InvocationResult",
    "ToolExecution",
    "VerificationRequest",
    "VerificationResult",
    "ApprovalRequest",
    "ApprovalResult",
    "AgentIdentity",
    "RegistryManifest",
    "DeploymentRequest",
    "DeploymentResponse",
    "ResourceRequirements",
    "AuthorityLevel",
    "RiskLevel",
    "VerificationMethod",
    "VerificationOutcome",
    "MemoryOp",
    "MemoryOpType",
    "MemoryResult",
]