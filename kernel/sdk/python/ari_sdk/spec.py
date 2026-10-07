"""
Agent Specification Builder - Fluent API for creating agent specs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

import yaml

from .types import (
    AgentSpec,
    InputSpec,
    OutputSpec,
    GovernanceSpec,
    MemorySpec,
    AuthorityLevel,
)


@dataclass
class SpecBuilder:
    """Fluent builder for agent specifications."""
    
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = "Unknown"
    spec_version: str = "1.0"
    capabilities: List[str] = field(default_factory=list)
    authority: AuthorityLevel = AuthorityLevel.L1
    schedule: str = "0 9 * * *"
    inputs: List[InputSpec] = field(default_factory=list)
    outputs: List[OutputSpec] = field(default_factory=list)
    governance: GovernanceSpec = field(default_factory=GovernanceSpec)
    memory: MemorySpec = field(default_factory=MemorySpec)

    def version(self, version: str) -> SpecBuilder:
        """Set agent version."""
        self.version = version
        return self

    def description(self, description: str) -> SpecBuilder:
        """Set agent description."""
        self.description = description
        return self

    def author(self, author: str) -> SpecBuilder:
        """Set agent author."""
        self.author = author
        return self

    def capability(self, capability: str) -> SpecBuilder:
        """Add a capability."""
        if capability not in self.capabilities:
            self.capabilities.append(capability)
        return self

    def capabilities(self, capabilities: List[str]) -> SpecBuilder:
        """Add multiple capabilities."""
        for cap in capabilities:
            self.capability(cap)
        return self

    def authority(self, level: AuthorityLevel) -> SpecBuilder:
        """Set authority level."""
        self.authority = level
        return self

    def schedule(self, cron: str) -> SpecBuilder:
        """Set schedule (cron expression)."""
        self.schedule = cron
        return self

    def input(self, name: str, type: str, required: bool, description: str) -> SpecBuilder:
        """Add an input."""
        self.inputs.append(InputSpec(
            name=name,
            type=type,
            required=required,
            description=description,
        ))
        return self

    def required_input(self, name: str, type: str, description: str) -> SpecBuilder:
        """Add a required input."""
        return self.input(name, type, True, description)

    def optional_input(self, name: str, type: str, description: str) -> SpecBuilder:
        """Add an optional input."""
        return self.input(name, type, False, description)

    def inputs(self, inputs: List[InputSpec]) -> SpecBuilder:
        """Add multiple inputs."""
        self.inputs.extend(inputs)
        return self

    def output(self, name: str, type: str, description: str) -> SpecBuilder:
        """Add an output."""
        self.outputs.append(OutputSpec(
            name=name,
            type=type,
            description=description,
        ))
        return self

    def decision_output(self, type: str = "object", description: str = "Agent decision") -> SpecBuilder:
        """Add a decision output."""
        return self.output("decision", type, description)

    def outputs(self, outputs: List[OutputSpec]) -> SpecBuilder:
        """Add multiple outputs."""
        self.outputs.extend(outputs)
        return self

    def governance(self, **kwargs: Any) -> SpecBuilder:
        """Set governance limits."""
        for key, value in kwargs.items():
            if hasattr(self.governance, key):
                setattr(self.governance, key, value)
        return self

    def max_tool_calls(self, max: int) -> SpecBuilder:
        """Set max tool calls."""
        self.governance.max_tool_calls = max
        return self

    def max_cost_usd(self, cost: float) -> SpecBuilder:
        """Set max cost in USD."""
        self.governance.max_cost_usd = cost
        return self

    def max_execution_time_ms(self, ms: int) -> SpecBuilder:
        """Set max execution time in ms."""
        self.governance.max_execution_time_ms = ms
        return self

    def requires_approval_above_usd(self, amount: float) -> SpecBuilder:
        """Set approval threshold."""
        self.governance.requires_approval_above_usd = amount
        return self

    def memory_backend(self, backend: str) -> SpecBuilder:
        """Set memory backend."""
        self.memory.backend = backend
        return self

    def memory_ttl_days(self, days: int) -> SpecBuilder:
        """Set memory TTL in days."""
        self.memory.ttl_days = days
        return self

    def build(self) -> AgentSpec:
        """Build the final spec."""
        if not self.name:
            raise ValueError("Agent name is required")
        if not self.version:
            raise ValueError("Agent version is required")
        if not self.capabilities:
            raise ValueError("At least one capability is required")

        return AgentSpec(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author,
            spec_version=self.spec_version,
            capabilities=self.capabilities,
            authority=self.authority,
            schedule=self.schedule,
            inputs=self.inputs,
            outputs=self.outputs,
            governance=self.governance,
            memory=self.memory,
        )

    def to_yaml(self) -> str:
        """Export to YAML string."""
        spec = self.build()
        return yaml.dump(spec.model_dump(mode="json"), indent=2, sort_keys=False)

    def to_json(self) -> str:
        """Export to JSON string."""
        spec = self.build()
        return spec.model_dump_json(indent=2)


def create_agent_spec(
    name: str,
    version: str = "0.1.0",
    description: str = "",
    author: str = "Unknown",
) -> SpecBuilder:
    """Create a new agent specification builder."""
    return SpecBuilder(
        name=name,
        version=version,
        description=description,
        author=author,
    )


def create_agent(name: str, **kwargs: Any) -> SpecBuilder:
    """Quick create with minimal options."""
    return SpecBuilder(name=name, **kwargs)


# Predefined templates
class Templates:
    @staticmethod
    def data_analyst(name: str) -> SpecBuilder:
        """Data analysis agent template."""
        return create_agent(name) \
            .description("Analyzes data and provides insights") \
            .capabilities(["http", "crm"]) \
            .authority(AuthorityLevel.L2) \
            .required_input("dataset", "string", "Dataset identifier") \
            .optional_input("parameters", "object", "Analysis parameters") \
            .decision_output()

    @staticmethod
    def notifier(name: str) -> SpecBuilder:
        """Notification agent template."""
        return create_agent(name) \
            .description("Sends notifications based on triggers") \
            .capabilities(["email", "slack"]) \
            .authority(AuthorityLevel.L1) \
            .required_input("event", "object", "Trigger event") \
            .optional_input("recipients", "array", "Notification recipients") \
            .decision_output()

    @staticmethod
    def crm_automation(name: str) -> SpecBuilder:
        """CRM automation agent template."""
        return create_agent(name) \
            .description("Automates CRM workflows") \
            .capabilities(["crm", "email"]) \
            .authority(AuthorityLevel.L3) \
            .required_input("context", "object", "Execution context") \
            .decision_output() \
            .governance(max_tool_calls=50, max_cost_usd=5.0)

    @staticmethod
    def generic(name: str) -> SpecBuilder:
        """Generic template."""
        return create_agent(name) \
            .description("A generic ARI agent") \
            .capabilities(["http"]) \
            .authority(AuthorityLevel.L1) \
            .required_input("context", "object", "Execution context") \
            .decision_output()


def validate_spec(spec: AgentSpec) -> Dict[str, Any]:
    """Validate an agent spec."""
    errors: List[str] = []
    warnings: List[str] = []

    if not spec.name or not spec.name.strip():
        errors.append("name is required")
    if not spec.version or not spec.version.strip():
        errors.append("version is required")
    if not spec.description or not spec.description.strip():
        errors.append("description is required")
    if not spec.author or not spec.author.strip():
        errors.append("author is required")
    if not spec.spec_version or not spec.spec_version.strip():
        errors.append("spec_version is required")
    if not spec.capabilities or len(spec.capabilities) == 0:
        errors.append("at least one capability is required")
    if not spec.authority or not spec.authority.strip():
        errors.append("authority is required")
    if not spec.schedule or not spec.schedule.strip():
        errors.append("schedule is required")

    valid_authorities = [level.value for level in AuthorityLevel]
    if spec.authority and spec.authority not in valid_authorities:
        errors.append(f"invalid authority: {spec.authority}")

    if spec.governance:
        if spec.governance.max_tool_calls == 0:
            errors.append("max_tool_calls must be > 0")
        if spec.governance.max_tool_calls > 100:
            warnings.append("max_tool_calls > 100 may cause runaway executions")
        if spec.governance.max_cost_usd <= 0:
            errors.append("max_cost_usd must be > 0")
        if spec.governance.max_cost_usd > 100:
            warnings.append("max_cost_usd > $100 - ensure budget controls")
        if spec.governance.max_execution_time_ms == 0:
            errors.append("max_execution_time_ms must be > 0")

    if spec.capabilities and len(spec.capabilities) > 20:
        warnings.append("many capabilities may increase attack surface")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }