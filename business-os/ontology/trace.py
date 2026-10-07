"""
Trace — generation, propagation, chain construction.

Every action in SmartDecigen carries a trace_id that chains through
Mission → Goal → Capability → Executive → Tool → Evidence → Outcome.

Without tracing, SmartDecigen is a black box. With it, it's auditable.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel, Field


# Create a unique trace identifier.
def generate_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


# Current UTC timestamp.
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# One auditable hop in the execution chain.
class TraceStep(BaseModel):
    layer: str
    entity_id: str
    entity_type: str
    timestamp: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# A recorded decision with rationale and alternatives.
class DecisionLog(BaseModel):
    decision: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    authority_level: str = "L3"
    made_at: datetime = Field(default_factory=utcnow)


class Trace(BaseModel):
    """Immutable execution trace — every action writes to this chain."""
    trace_id: str = Field(default_factory=generate_trace_id)
    mission_id: Optional[str] = None
    goal_id: Optional[str] = None
    project_id: Optional[str] = None
    capability_name: Optional[str] = None
    executive_id: Optional[str] = None
    tool_slug: Optional[str] = None
    steps: list[TraceStep] = Field(default_factory=list)
    decisions: list[DecisionLog] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)

    # Append a layer event to the trace chain.
    def add_step(self, layer: str, entity_id: str, entity_type: str, **meta) -> "Trace":
        self.steps.append(TraceStep(layer=layer, entity_id=entity_id, entity_type=entity_type, metadata=meta))
        return self

    # Append a decision record to the trace.
    def add_decision(self, decision: str, rationale: str, alternatives: list[str] = None,
                     confidence: float = 0.5, authority: str = "L3") -> "Trace":
        self.decisions.append(DecisionLog(
            decision=decision, rationale=rationale,
            alternatives=alternatives or [], confidence=confidence,
            authority_level=authority
        ))
        return self

    def chain(self) -> str:
        """Render the full trace chain: Mission → Goal → ... → Outcome."""
        nodes = []
        if self.mission_id:
            nodes.append(f"Mission({self.mission_id})")
        if self.goal_id:
            nodes.append(f"Goal({self.goal_id})")
        if self.project_id:
            nodes.append(f"Project({self.project_id})")
        if self.capability_name:
            nodes.append(f"Capability({self.capability_name})")
        if self.executive_id:
            nodes.append(f"Executive({self.executive_id})")
        if self.tool_slug:
            nodes.append(f"Tool({self.tool_slug})")
        for step in self.steps:
            nodes.append(f"{step.entity_type}({step.entity_id})")
        return " → ".join(nodes)

    # Serialize the trace to a JSON-safe dict.
    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


def new_trace(mission_id: str = None, goal_id: str = None) -> Trace:
    """Create a new trace chained to a mission and goal."""
    return Trace(mission_id=mission_id, goal_id=goal_id)


# ── demo ──
def _demo():
    t = (
        new_trace(mission_id="mission_abc", goal_id="goal_xyz")
        .add_step("Capability Registry", "cap_001", "Capability", matched_capability="Customer Communication")
        .add_step("Tool Intelligence Engine", "tie_call_1", "TIE", selected_tool="GMAIL_SEND_EMAIL", score=0.92)
        .add_step("Execution Runtime", "exec_001", "Execution", elapsed_ms=450)
        .add_step("Verification Runtime", "ev_001", "Verification", outcome="SUCCESS")
        .add_decision("Use Gmail for customer outreach", "Connected account + 0.92 reliability score",
                       ["Outlook (0.75)", "Slack (0.60)"], confidence=0.92, authority="L1")
    )
    chain = t.chain()
    assert "mission_abc" in chain
    assert "Capability" in chain
    tie_step = t.steps[1]
    assert tie_step.metadata.get("selected_tool") == "GMAIL_SEND_EMAIL"
    assert len(t.steps) == 4
    assert len(t.decisions) == 1
    return {"trace_id": t.trace_id, "chain": chain, "steps": len(t.steps), "status": "OK"}


if __name__ == "__main__":
    import json
    print(json.dumps(_demo(), indent=2, default=str))
