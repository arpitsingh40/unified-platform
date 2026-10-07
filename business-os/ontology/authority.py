"""
Authority Gradient — L0 to L5 enforcement.

Every action carries an authority_level. This module provides the
enforcer that gates execution based on the executive's authorized level.

Levels:
  L0 — Observe only (read-only access to data)
  L1 — Execute automatically (trusted autonomous actions)
  L2 — Execute with notification (autonomous, founder informed)
  L3 — Recommend (proposes action, founder/executive approves)
  L4 — Escalate (proposes action to founder, founder must approve)
  L5 — Restricted (founder only — strategic/irreversible decisions)
"""

from __future__ import annotations
from enum import Enum
from functools import wraps
from typing import Callable, Any


# L0–L5 authority levels, ordered from observation to founder-only.
class AuthorityLevel(str, Enum):
    L0_OBSERVE = "L0"
    L1_EXECUTE = "L1"
    L2_EXECUTE_NOTIFY = "L2"
    L3_RECOMMEND = "L3"
    L4_ESCALATE = "L4"
    L5_RESTRICTED = "L5"


# Numeric privilege rank for comparing authority levels.
AUTHORITY_ORDER = {
    AuthorityLevel.L0_OBSERVE: 0,
    AuthorityLevel.L1_EXECUTE: 1,
    AuthorityLevel.L2_EXECUTE_NOTIFY: 2,
    AuthorityLevel.L3_RECOMMEND: 3,
    AuthorityLevel.L4_ESCALATE: 4,
    AuthorityLevel.L5_RESTRICTED: 5,
}


# Human-readable label and description for each authority level.
AUTHORITY_LABELS = {
    AuthorityLevel.L0_OBSERVE: ("Observe only", "Read-only. No actions taken."),
    AuthorityLevel.L1_EXECUTE: ("Execute automatically", "Trusted autonomous execution. No notification."),
    AuthorityLevel.L2_EXECUTE_NOTIFY: ("Execute + notify", "Autonomous. Founder is informed after."),
    AuthorityLevel.L3_RECOMMEND: ("Recommend", "Proposes action. Requires executive or founder approval."),
    AuthorityLevel.L4_ESCALATE: ("Escalate", "Proposes action. Founder must approve before execution."),
    AuthorityLevel.L5_RESTRICTED: ("Restricted", "Founder only. Irreversible or strategic decisions."),
}


def can_execute(required: AuthorityLevel, authorized: AuthorityLevel) -> bool:
    """Check if an executive with `authorized` level can perform an action requiring `required` level.
    Lower numbers = more trusted/higher privilege. An L1 executive can do L0, L1, L2.
    An L3 executive can do L0-L3. L4-L5 require founder."""
    return AUTHORITY_ORDER[authorized] >= AUTHORITY_ORDER[required]


def requires_review(level: AuthorityLevel) -> bool:
    """Returns True if this authority level requires human review before execution.
    L0-L2 are autonomous, L3-L5 require review."""
    return AUTHORITY_ORDER[level] >= AUTHORITY_ORDER[AuthorityLevel.L3_RECOMMEND]


def requires_founder(level: AuthorityLevel) -> bool:
    """Returns True if this authority level requires founder approval."""
    return AUTHORITY_ORDER[level] >= AUTHORITY_ORDER[AuthorityLevel.L4_ESCALATE]


def needs_notification(level: AuthorityLevel) -> bool:
    """Returns True if the founder should be notified when this level executes."""
    return AUTHORITY_ORDER[level] >= AUTHORITY_ORDER[AuthorityLevel.L2_EXECUTE_NOTIFY]


# Raised when an executive exceeds their authorized level.
class AuthorityError(Exception):
    def __init__(self, required: AuthorityLevel, authorized: AuthorityLevel, action: str = ""):
        self.required = required
        self.authorized = authorized
        self.action = action
        super().__init__(
            f"Authority denied for '{action}': requires {required.value} but authorized for {authorized.value}"
        )


def require(level: AuthorityLevel) -> Callable:
    """Decorator: gate a function behind an authority level.

    Usage:
        @require(AuthorityLevel.L1_EXECUTE)
        def send_email(to, subject, body, authority_level=AuthorityLevel.L0_OBSERVE):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            caller_level = kwargs.pop("_authority_level", AuthorityLevel.L0_OBSERVE)
            if not can_execute(level, caller_level):
                raise AuthorityError(required=level, authorized=caller_level, action=func.__name__)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def escalate(action_name: str, reason: str, required: AuthorityLevel = AuthorityLevel.L4_ESCALATE) -> dict:
    """Create an escalation record for founder review."""
    return {
        "action": action_name,
        "reason": reason,
        "required_authority": required.value,
        "status": "pending_founder_approval",
    }


# ── demo ──
def _demo():
    exec_level = AuthorityLevel.L1_EXECUTE

    results = {
        "L1 can execute L1": can_execute(AuthorityLevel.L1_EXECUTE, exec_level),
        "L1 cannot execute L5": not can_execute(AuthorityLevel.L5_RESTRICTED, exec_level),
        "L3 needs review": requires_review(AuthorityLevel.L3_RECOMMEND),
        "L5 needs founder": requires_founder(AuthorityLevel.L5_RESTRICTED),
        "L2 needs notification": needs_notification(AuthorityLevel.L2_EXECUTE_NOTIFY),
    }

    @require(AuthorityLevel.L1_EXECUTE)
    def test_action(_authority_level=AuthorityLevel.L0_OBSERVE):
        return "executed"

    try:
        test_action(_authority_level=exec_level)
        results["decorator_allows_L1"] = True
    except AuthorityError:
        results["decorator_allows_L1"] = False

    try:
        test_action(_authority_level=AuthorityLevel.L0_OBSERVE)
        results["decorator_blocks_L0"] = False
    except AuthorityError:
        results["decorator_blocks_L0"] = True

    esc = escalate("delete_production_db", "Irreversible action")
    results["escalation_generated"] = esc["status"] == "pending_founder_approval"

    assert all(results.values()), f"Authority tests failed: {results}"
    return {"authority_checks": results, "status": "OK"}


if __name__ == "__main__":
    import json
    print(json.dumps(_demo(), indent=2, default=str))
