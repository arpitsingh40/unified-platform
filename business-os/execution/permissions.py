"""Execution Permissions — authority gates for MCP tool execution.
Every tool call is checked against the calling executive's authority.
High-impact or irreversible actions require founder approval.

Permission model (hierarchical):
  1. Founder: all tools, no approval needed (override everything)
  2. Department head: tools scoped to their department, spending capped
  3. Executive: tools scoped to their role, spending capped, external = gated
  4. Member: no MCP access (read-only advisory from brain)
"""
import os
import logging
from typing import Optional

log = logging.getLogger("execution.permissions")

# ponytail: thresholds from env, defaults are conservative
FOUNDER_APPROVAL_THRESHOLD_INR = int(os.environ.get("MCP_APPROVAL_THRESHOLD_INR", "50000"))
IRREVERSIBLE_ACTIONS = os.environ.get("MCP_IRREVERSIBLE_ACTIONS",
    "github_delete_repo,github_remove_collaborator,stripe_refund,aws_terminate_instance,"
    "shopify_delete_product,salesforce_delete_record,notion_delete_page"
).split(",")

# ponytail: write-sensitive tool prefixes — these always need review
SENSITIVE_PREFIXES = ("delete", "remove", "terminate", "refund", "destroy", "purge", "revoke")


# Detect sensitive or irreversible tool names
def _is_sensitive(tool_name: str) -> bool:
    name_lower = tool_name.lower()
    if name_lower in IRREVERSIBLE_ACTIONS:
        return True
    return any(name_lower.startswith(p) for p in SENSITIVE_PREFIXES)


def _spending_from_args(args: dict) -> int:
    """Extract spending amount from tool arguments. Best-effort, not exhaustive."""
    for key in ("amount", "amount_inr", "price", "total", "value", "budget"):
        v = args.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def check_permission(
    tool_name: str,
    arguments: dict,
    caller_role: str = "member",
    executive_dna: Optional[dict] = None,
    founder_approved: bool = False,
) -> dict:
    """Check if this MCP tool call is authorized.
    Returns {"allowed": bool, "reason": str, "requires_approval": bool}
    """
    # Founder: always allowed
    if caller_role == "owner":
        return {"allowed": True, "reason": "owner", "requires_approval": False}

    # Members without executive DNA: no MCP access
    if not executive_dna:
        return {"allowed": False, "reason": "no_executive_role", "requires_approval": False}

    authority = executive_dna.get("authority", {})
    lifecycle_status = executive_dna.get("lifecycle", {}).get("status", "")

    # Archived or under review: no execution
    if lifecycle_status in ("archived", "under_review"):
        return {"allowed": False, "reason": f"executive_is_{lifecycle_status}", "requires_approval": False}

    # Probation: limited execution, all external comms gated
    if lifecycle_status == "probation" and not founder_approved:
        return {"allowed": False, "reason": "probation_requires_approval", "requires_approval": True}

    # Check spending limit
    spending = _spending_from_args(arguments)
    if spending > 0:
        limit = authority.get("spending_limit_inr", 0)
        if spending > limit:
            return {"allowed": False,
                    "reason": f"spending_exceeds_limit ({spending} > {limit})",
                    "requires_approval": True}

    # Check external communication
    external_tools = {"gmail", "linkedin", "twitter", "slack", "whatsapp", "calendar"}
    is_external = any(tool_name.lower().startswith(p) for p in external_tools)
    if is_external and not authority.get("can_communicate_externally", False):
        return {"allowed": False,
                "reason": "external_communication_not_authorized",
                "requires_approval": True}

    # Irreversible actions always need approval
    if _is_sensitive(tool_name) and not founder_approved:
        return {"allowed": False,
                "reason": f"irreversible_action_{tool_name}",
                "requires_approval": True}

    # Decision rights check
    decision_rights = authority.get("decision_rights", [])
    if decision_rights and not any(tool_name.lower().startswith(r.lower()) for r in decision_rights):
        return {"allowed": False,
                "reason": f"tool_not_in_decision_rights",
                "requires_approval": True}

    return {"allowed": True, "reason": "authorized", "requires_approval": False}


def requires_founder_review(tool_name: str, arguments: dict, spending_inr: int = 0) -> bool:
    """Quick pre-check: does this action need founder review regardless of executive role?"""
    if _is_sensitive(tool_name):
        return True
    if spending_inr > FOUNDER_APPROVAL_THRESHOLD_INR:
        return True
    return False
