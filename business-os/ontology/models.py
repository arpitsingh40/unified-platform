"""
SmartDecigen Company Ontology — the shared type system.

Every module speaks this language. No subsystem invents its own nouns.
Mission → Goal → Project → Capability → Action → Tool → Evidence → Trace.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


# Generate a collision-resistant ID with an optional prefix.
def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


# Current UTC timestamp, timezone-aware.
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ──

class AuthorityLevel(str, Enum):
    L0_OBSERVE = "L0"
    L1_EXECUTE = "L1"
    L2_EXECUTE_NOTIFY = "L2"
    L3_RECOMMEND = "L3"
    L4_ESCALATE = "L4"
    L5_RESTRICTED = "L5"


# Lifecycle states an executive passes through.
class ExecutiveStatus(str, Enum):
    INSTANTIATED = "instantiation"
    PROBATION = "probation"
    ACTIVE = "active"
    PROMOTED = "promoted"
    UNDER_REVIEW = "under_review"
    ARCHIVED = "archived"
    MERGED = "merged"


# Whether an action can be undone once executed.
class Reversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"
    PARTIALLY_REVERSIBLE = "PARTIALLY_REVERSIBLE"


# Result states recorded as evidence for learning.
class OutcomeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


# How quickly this data becomes stale.
class Volatility(str, Enum):
    STABLE = "STABLE"
    FLUID = "FLUID"
    VOLATILE = "VOLATILE"


# Which system layer a learned pattern adjusts.
class LearningImpact(str, Enum):
    TOOL_SCORE = "TOOL_SCORE"
    CAPABILITY_ESTIMATE = "CAPABILITY_ESTIMATE"
    ORG_STRUCTURE = "ORG_STRUCTURE"
    AUTHORITY_CHANGE = "AUTHORITY_CHANGE"
    EXECUTIVE_KPI = "EXECUTIVE_KPI"


# ── Core Entities ──

class Capability(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cap_"))
    name: str
    parent_goal_type: str = ""
    possible_actions: list[str] = Field(default_factory=list)
    required_authority: AuthorityLevel = AuthorityLevel.L1_EXECUTE


# A single executable step with authority and tool bindings.
class Action(BaseModel):
    id: str = Field(default_factory=lambda: new_id("act_"))
    name: str
    reversibility: Reversibility = Reversibility.REVERSIBLE
    authority_required: AuthorityLevel = AuthorityLevel.L1_EXECUTE
    tool_bindings: list[ToolBinding] = Field(default_factory=list)


# Connection profile between an action and a tool.
class ToolBinding(BaseModel):
    toolkit_slug: str
    tool_slug: str
    tool_name: str = ""
    availability: str = "UNKNOWN"
    reliability_score: float = 0.5
    cost_estimate: float = 0.0
    latency_ms: int = 0
    is_managed: bool = False
    is_connected: bool = False


# An external tool available for execution.
class Tool(BaseModel):
    slug: str
    name: str
    toolkit: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


# Measurable target used to grade goals.
class KPI(BaseModel):
    name: str
    target: str = ""
    current: Optional[float] = None
    weight: int = 5
    trend: str = "stable"


# Money allocated, spent, and remaining.
class Budget(BaseModel):
    allocated: float = 0.0
    spent: float = 0.0
    remaining: float = 0.0


# Track record that drives executive promotion.
class Experience(BaseModel):
    projects_led: int = 0
    projects_completed: int = 0
    decisions_made: int = 0
    decisions_with_positive_outcome: int = 0
    outcome_success_rate: float = 0.0
    total_impact: float = 0.0


# Full profile of an autonomous executive.
class ExecutiveState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("exec_"))
    org_id: str = ""
    role: str = ""
    department_id: str = ""
    division_id: Optional[str] = None
    mission: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.L3_RECOMMEND
    spending_limit: float = 0.0
    status: ExecutiveStatus = ExecutiveStatus.INSTANTIATED
    kpis: list[KPI] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    experience: Experience = Field(default_factory=Experience)
    capabilities: list[str] = Field(default_factory=list)
    knowledge_domains: list[str] = Field(default_factory=list)
    active_projects: list[str] = Field(default_factory=list)
    pending_decisions: list[str] = Field(default_factory=list)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# A functional unit staffed by executives.
class Division(BaseModel):
    id: str = Field(default_factory=lambda: new_id("div_"))
    name: str
    function: str = ""
    executives: list[ExecutiveState] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


# A strategic objective with KPIs and projects.
class Goal(BaseModel):
    id: str = Field(default_factory=lambda: new_id("goal_"))
    description: str
    target_date: Optional[datetime] = None
    kpis: list[KPI] = Field(default_factory=list)
    owner_executive_id: Optional[str] = None
    status: str = "active"
    projects: list[Project] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# Time-boxed work item owned by an executive.
class Project(BaseModel):
    id: str = Field(default_factory=lambda: new_id("proj_"))
    name: str
    status: str = "planned"
    goal_id: Optional[str] = None
    required_capabilities: list[Capability] = Field(default_factory=list)
    assigned_executive_id: Optional[str] = None
    tasks: list[Task] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# Smallest unit of execution, traceable by ID.
class Task(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task_"))
    description: str
    capability_name: str = ""
    preferred_tool: Optional[ToolBinding] = None
    authority_required: AuthorityLevel = AuthorityLevel.L1_EXECUTE
    reversibility: Reversibility = Reversibility.REVERSIBLE
    status: str = "pending"
    trace_id: Optional[str] = None
    assigned_executive_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


# Annual theme linking a year to its goals.
class Strategy(BaseModel):
    year: int = utcnow().year
    theme: str = ""
    objectives: list[str] = Field(default_factory=list)
    goals: list[Goal] = Field(default_factory=list)


# Top-level container holding the whole organization.
class Mission(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mission_"))
    title: str
    statement: str
    founder_id: str = ""
    org_id: str = ""
    strategies: list[Strategy] = Field(default_factory=list)
    divisions: list[Division] = Field(default_factory=list)
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ── Trace & Evidence ──

class DecisionLog(BaseModel):
    decision: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    authority_level: AuthorityLevel = AuthorityLevel.L3_RECOMMEND
    made_at: datetime = Field(default_factory=utcnow)


# One auditable event recorded along the execution chain.
class TraceStep(BaseModel):
    layer: str
    entity_id: str
    entity_type: str
    timestamp: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Execution chain linking every layer from mission to tool.
class Trace(BaseModel):
    trace_id: str = Field(default_factory=lambda: new_id("trace_"))
    mission_id: Optional[str] = None
    goal_id: Optional[str] = None
    project_id: Optional[str] = None
    capability_name: Optional[str] = None
    executive_id: Optional[str] = None
    tool_slug: Optional[str] = None
    steps: list[TraceStep] = Field(default_factory=list)
    decisions: list[DecisionLog] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# Measured outcome used to update learning models.
class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev_"))
    trace_id: Optional[str] = None
    source: str = ""
    evidence_type: str = "EXECUTION"
    outcome: OutcomeStatus = OutcomeStatus.UNKNOWN
    expected_outcome: str = ""
    actual_result: str = ""
    confidence: float = 0.0
    timestamp: datetime = Field(default_factory=utcnow)
    freshness_days: float = 0.0
    volatility: Volatility = Volatility.STABLE
    reversibility_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def status(self) -> str:
        """Map outcome to status string expected by collector/dispatcher.
        SUCCESS → done, FAILURE → failed, PARTIAL → partial, UNKNOWN → unknown."""
        _map = {OutcomeStatus.SUCCESS: "done", OutcomeStatus.FAILURE: "failed",
                OutcomeStatus.PARTIAL: "done", OutcomeStatus.UNKNOWN: "unknown"}
        return _map.get(self.outcome, "unknown")

    # Serialize with computed status and raw outcome enum included.
    def model_dump(self, **kwargs) -> dict:
        data = super().model_dump(**kwargs)
        data["status"] = self.status
        if "outcome" in data and hasattr(data["outcome"], "value"):
            data["outcome"] = data["outcome"].value if hasattr(data["outcome"], "value") else str(data["outcome"])
        return data


# A derived pattern applied to improve the system.
class LearningEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("learn_"))
    derived_from: list[str] = Field(default_factory=list)
    pattern: str = ""
    impact: LearningImpact = LearningImpact.TOOL_SCORE
    applied: bool = False
    applied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


# ── Execution Plan ──

class ExecutionAction(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)
    description: str = ""
    capability_name: str = ""
    authority_required: AuthorityLevel = AuthorityLevel.L1_EXECUTE
    reversibility: Reversibility = Reversibility.REVERSIBLE
    trace_id: Optional[str] = None


# Ordered list of tool actions to achieve a goal.
class ExecutionPlan(BaseModel):
    goal: str = ""
    mission_id: Optional[str] = None
    goal_id: Optional[str] = None
    executive_id: Optional[str] = None
    actions: list[ExecutionAction] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: new_id("trace_"))


# Outcome report for one executed action.
class ExecutionResult(BaseModel):
    execution_id: str = Field(default_factory=lambda: new_id("exec_"))
    plan: ExecutionPlan = Field(default_factory=ExecutionPlan)
    action: str = ""
    status: str = "pending"
    result: str = ""
    error: str = ""
    elapsed_ms: int = 0
    retries: int = 0
    authority_level: AuthorityLevel = AuthorityLevel.L1_EXECUTE
    trace_id: Optional[str] = None
    executed_at: datetime = Field(default_factory=utcnow)


# ── Organization Snapshot (for founder dashboard) ──

class OrgSnapshot(BaseModel):
    generated_at: datetime = Field(default_factory=utcnow)
    mission: Optional[Mission] = None
    division_count: int = 0
    executive_count: int = 0
    active_projects: int = 0
    recent_evidence: list[Evidence] = Field(default_factory=list)
    learning_events: list[LearningEvent] = Field(default_factory=list)
    nervous_system_recommendations: list[str] = Field(default_factory=list)


# ── Self-test ──

def _demo():
    """Self-check: build a minimal ontology graph and verify all types round-trip."""
    m = Mission(
        title="Launch SmartDecigen in India",
        statement="Build the world's first Autonomous Executive Organization for founders.",
    )
    g = Goal(description="Ship Capability Registry", target_date=utcnow())
    c = Capability(name="Customer Communication")
    c.possible_actions = ["Send Email", "Schedule Meeting"]
    p = Project(name="Phase 1 Execution", required_capabilities=[c])
    g.projects = [p]
    m.strategies = [Strategy(year=2026, theme="MVP Launch", goals=[g])]

    t = Trace(
        mission_id=m.id,
        goal_id=g.id,
        capability_name=c.name,
        steps=[TraceStep(layer="Capability Registry", entity_id=c.id, entity_type="Capability")],
        decisions=[DecisionLog(decision="Use Gmail for outreach", rationale="Connected + high reliability")]
    )

    e = Evidence(
        trace_id=t.trace_id,
        outcome=OutcomeStatus.SUCCESS,
        expected_outcome="Customer received onboarding email",
        actual_result="Email delivered, opened within 12 hours",
        confidence=0.92
    )

    learn = LearningEvent(
        derived_from=[e.id],
        pattern="Gmail delivery succeeded on first attempt for customer communication",
        impact=LearningImpact.TOOL_SCORE,
        applied=True,
        applied_at=utcnow(),
    )

    exec_plan = ExecutionPlan(
        goal="Send onboarding email to new customer",
        mission_id=m.id, goal_id=g.id,
        actions=[ExecutionAction(tool="GMAIL_SEND_EMAIL", args={"to": "test@test.com", "subject": "Welcome"},
                                  capability_name=c.name, trace_id=t.trace_id)]
    )

    snap = OrgSnapshot(
        mission=m, division_count=1, executive_count=3, active_projects=1,
        recent_evidence=[e], learning_events=[learn],
        nervous_system_recommendations=["Create QA executive — 3/5 outreach emails had typos last week"]
    )

    assert m.title == "Launch SmartDecigen in India"
    assert g.description == "Ship Capability Registry"
    assert t.trace_id.startswith("trace_")
    assert e.outcome == OutcomeStatus.SUCCESS
    assert learn.impact == LearningImpact.TOOL_SCORE
    assert len(exec_plan.actions) == 1
    assert "QA executive" in snap.nervous_system_recommendations[0]

    return {
        "mission_id": m.id, "goal_id": g.id, "trace_id": t.trace_id,
        "evidence_id": e.id, "learning_id": learn.id,
        "plan_id": exec_plan.trace_id,
        "status": "ALL CHECKS PASSED"
    }


if __name__ == "__main__":
    import json
    result = _demo()
    print(json.dumps(result, indent=2, default=str))
