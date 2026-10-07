"""
SmartDecigen Ontology — re-export all types.

This is the single import point for every module in SmartDecigen:
    from ontology import Mission, Goal, Trace, Evidence, ...
"""

from .models import (
    new_id, utcnow,
    AuthorityLevel, ExecutiveStatus, Reversibility, OutcomeStatus, Volatility, LearningImpact,
    Capability, Action, ToolBinding, Tool, KPI, Budget, Experience,
    ExecutiveState, Division, Goal, Project, Task,
    Strategy, Mission,
    DecisionLog, TraceStep, Trace,
    Evidence, LearningEvent,
    ExecutionAction, ExecutionPlan, ExecutionResult,
    OrgSnapshot,
    _demo as _models_demo,
)

from .trace import (
    generate_trace_id, new_trace,
    TraceStep as TraceStepStandalone,
    DecisionLog as DecisionLogStandalone,
    Trace as TraceStandalone,
)

from .authority import (
    AuthorityLevel as AuthLevel,
    AUTHORITY_ORDER, AUTHORITY_LABELS,
    can_execute, requires_review, requires_founder, needs_notification,
    AuthorityError, require, escalate,
)

from .temporal import (
    iso_now, age_days, age_hours,
    freshness_score, is_stale, decay_weight, format_age,
    week_start, quarter_start, quarter_label, next_review_date,
    Volatility as TemporalVolatility,
)

# Central public API — every name importers may pull from this package.
__all__ = [
    # Core types
    "new_id", "utcnow",
    "AuthorityLevel", "ExecutiveStatus", "Reversibility", "OutcomeStatus", "Volatility", "LearningImpact",
    "Capability", "Action", "ToolBinding", "Tool", "KPI", "Budget", "Experience",
    "ExecutiveState", "Division", "Goal", "Project", "Task",
    "Strategy", "Mission",
    "DecisionLog", "TraceStep", "Trace",
    "Evidence", "LearningEvent",
    "ExecutionAction", "ExecutionPlan", "ExecutionResult",
    "OrgSnapshot",
    # Trace
    "generate_trace_id", "new_trace",
    # Authority
    "AUTHORITY_ORDER", "AUTHORITY_LABELS",
    "can_execute", "requires_review", "requires_founder", "needs_notification",
    "AuthorityError", "require", "escalate",
    # Temporal
    "iso_now", "age_days", "age_hours",
    "freshness_score", "is_stale", "decay_weight", "format_age",
    "week_start", "quarter_start", "quarter_label", "next_review_date",
]
