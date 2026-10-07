"""
ARI Python Client - Interact with the ARI runtime, registry, and control plane
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .types import (
    AriClientConfig,
    AgentInput,
    AgentResult,
    AgentDecision,
    ToolCall,
    ToolResult,
    InvocationRequest,
    InvocationResult,
    ToolExecution,
    VerificationResult,
    RegistryManifest,
    DeploymentRequest,
    DeploymentResponse,
    ResourceRequirements,
    AriError,
    NotFoundError,
    AuthorizationError,
    RuntimeError as AriRuntimeError,
)


class AriClient:
    """Client for interacting with ARI runtime, registry, and control plane."""

    def __init__(self, config: Optional[AriClientConfig] = None):
        self.config = config or AriClientConfig()
        
        common_headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            common_headers["Authorization"] = f"Bearer {self.config.api_key}"

        self._runtime = httpx.AsyncClient(
            base_url=self.config.runtime_url,
            timeout=self.config.timeout,
            headers=common_headers,
        )
        self._registry = httpx.AsyncClient(
            base_url=self.config.registry_url,
            timeout=self.config.timeout,
            headers=common_headers,
        )
        self._control_plane = httpx.AsyncClient(
            base_url=self.config.control_plane_url,
            timeout=self.config.timeout,
            headers=common_headers,
        )

    async def __aenter__(self) -> AriClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Close all HTTP clients."""
        await self._runtime.aclose()
        await self._registry.aclose()
        await self._control_plane.aclose()

    # =============================================================================
    # Runtime API
    # =============================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError))
    )
    async def invoke(self, request: InvocationRequest) -> InvocationResult:
        """Invoke an agent."""
        try:
            response = await self._runtime.post(
                "/api/v1/invoke",
                json=request.model_dump(mode="json")
            )
            response.raise_for_status()
            return InvocationResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError("Agent or endpoint")
            if e.response.status_code == 401:
                raise AuthorizationError()
            raise AriRuntimeError(
                e.response.json().get("message", str(e)) if e.response.content else str(e)
            )

    async def run(
        self,
        agent_id: str,
        context: Dict[str, Any],
        org_id: str = "default",
        invocation_id: Optional[str] = None,
        trace_parent: Optional[str] = None,
        dry_run: bool = False,
    ) -> InvocationResult:
        """Run an agent with simple context (convenience method)."""
        request = InvocationRequest(
            invocation_id=invocation_id or f"inv_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            org_id=org_id,
            context=context,
            trace_parent=trace_parent,
        )
        return await self.invoke(request)

    async def get_invocation(self, invocation_id: str) -> InvocationResult:
        """Get invocation status."""
        response = await self._runtime.get(f"/api/v1/invocations/{invocation_id}")
        response.raise_for_status()
        return InvocationResult(**response.json())

    async def list_invocations(
        self,
        agent_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[InvocationResult]:
        """List invocations for an agent."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        
        response = await self._runtime.get(
            f"/api/v1/agents/{agent_id}/invocations",
            params=params
        )
        response.raise_for_status()
        return [InvocationResult(**item) for item in response.json()]

    # =============================================================================
    # Tool Execution
    # =============================================================================

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call directly."""
        response = await self._runtime.post(
            "/api/v1/tools/execute",
            json=tool_call.model_dump(mode="json")
        )
        response.raise_for_status()
        return ToolResult(**response.json())

    # =============================================================================
    # Registry API
    # =============================================================================

    async def get_manifest(self, name: str, version: str) -> RegistryManifest:
        """Get agent manifest from registry."""
        try:
            response = await self._registry.get(f"/api/v1/manifests/{name}/{version}")
            response.raise_for_status()
            return RegistryManifest(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NotFoundError(f"Agent {name}:{version}")
            raise

    async def search_agents(
        self,
        query: str,
        capability: Optional[str] = None,
        authority: Optional[str] = None,
        limit: int = 20,
    ) -> List[RegistryManifest]:
        """Search agents in registry."""
        params = {"q": query, "limit": limit}
        if capability:
            params["capability"] = capability
        if authority:
            params["authority"] = authority

        response = await self._registry.get("/api/v1/search", params=params)
        response.raise_for_status()
        return [RegistryManifest(**item) for item in response.json()]

    async def list_versions(self, name: str) -> List[str]:
        """List all versions of an agent."""
        response = await self._registry.get(f"/api/v1/agents/{name}/versions")
        response.raise_for_status()
        return response.json()

    # =============================================================================
    # Control Plane API
    # =============================================================================

    async def deploy(self, request: DeploymentRequest) -> DeploymentResponse:
        """Deploy an agent."""
        response = await self._control_plane.post(
            "/api/v1/deployments",
            json=request.model_dump(mode="json")
        )
        response.raise_for_status()
        return DeploymentResponse(**response.json())

    async def get_deployment(self, deployment_id: str) -> DeploymentResponse:
        """Get deployment status."""
        response = await self._control_plane.get(f"/api/v1/deployments/{deployment_id}")
        response.raise_for_status()
        return DeploymentResponse(**response.json())

    async def scale_deployment(
        self,
        deployment_id: str,
        replicas: int
    ) -> DeploymentResponse:
        """Scale a deployment."""
        response = await self._control_plane.patch(
            f"/api/v1/deployments/{deployment_id}/scale",
            json={"replicas": replicas}
        )
        response.raise_for_status()
        return DeploymentResponse(**response.json())

    async def delete_deployment(self, deployment_id: str) -> None:
        """Delete a deployment."""
        response = await self._control_plane.delete(f"/api/v1/deployments/{deployment_id}")
        response.raise_for_status()

    async def list_deployments(
        self,
        environment: Optional[str] = None,
        agent_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[DeploymentResponse]:
        """List deployments."""
        params = {}
        if environment:
            params["environment"] = environment
        if agent_name:
            params["agent_name"] = agent_name
        if status:
            params["status"] = status

        response = await self._control_plane.get("/api/v1/deployments", params=params)
        response.raise_for_status()
        return [DeploymentResponse(**item) for item in response.json()]

    async def get_deployment_logs(
        self,
        deployment_id: str,
        tail: int = 100,
        since: Optional[str] = None,
    ) -> str:
        """Get deployment logs."""
        params = {"tail": tail}
        if since:
            params["since"] = since

        response = await self._control_plane.get(
            f"/api/v1/deployments/{deployment_id}/logs",
            params=params
        )
        response.raise_for_status()
        return response.text

    # =============================================================================
    # Health & Metrics
    # =============================================================================

    async def health_check(self) -> Dict[str, Any]:
        """Check runtime health."""
        response = await self._runtime.get("/health")
        response.raise_for_status()
        return response.json()

    async def get_metrics(self) -> Dict[str, Any]:
        """Get runtime metrics."""
        response = await self._runtime.get("/metrics")
        response.raise_for_status()
        return response.json()

    # =============================================================================
    # Utility Methods
    # =============================================================================

    @staticmethod
    def create_decision(
        action: str,
        reasoning: str,
        tool_calls: List[ToolCall],
        confidence: float = 0.8,
        review_after_days: int = 1,
    ) -> AgentDecision:
        """Create a default agent decision (for testing)."""
        return AgentDecision(
            action=action,
            reasoning=reasoning,
            tool_calls=tool_calls,
            confidence=confidence,
            review_after_days=review_after_days,
        )

    @staticmethod
    def create_tool_call(
        capability: str,
        tool: str,
        args: Dict[str, Any],
        reason: str = "",
    ) -> ToolCall:
        """Create a tool call."""
        return ToolCall(
            capability=capability,
            tool=tool,
            args=args,
            reason=reason,
        )

    @staticmethod
    def create_invocation(
        agent_id: str,
        org_id: str,
        context: Dict[str, Any],
    ) -> InvocationRequest:
        """Create an invocation request."""
        return InvocationRequest(
            invocation_id=f"inv_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            org_id=org_id,
            context=context,
        )


def create_client(config: Optional[AriClientConfig] = None) -> AriClient:
    """Create a new ARI client."""
    return AriClient(config)
# Enterprise helper — monkey-patched onto AriClient
def _set_token(self, token: str):
    self._runtime.headers['Authorization'] = f'Bearer {token}'
    for attr in ('_registry','_control_plane'):
        if hasattr(self, attr): getattr(self, attr).headers['Authorization'] = f'Bearer {token}'
AriClient.set_token = _set_token  # type: ignore
