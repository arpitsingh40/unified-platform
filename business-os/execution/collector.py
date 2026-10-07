"""Result Collector — captures MCP execution results, logs evidence,
feeds the Verification Engine and Decision Ledger.

Every tool execution becomes a tracked event:
  execution_id → tool, args, result, elapsed, evidence → outcome → learning

This is the bridge from "tool called" to "organization learned."
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("execution.collector")


# ISO timestamp helper
def now_iso():
    return datetime.now(timezone.utc).isoformat()


# Package execution result into evidence record
def collect_execution_result(
    action_result: dict,
    thread_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
    executive_id: Optional[str] = None,
) -> dict:
    """Package an execution result into a verifiable evidence record.
    This feeds into: Decision Ledger, Verification Engine, Outcome Tracking.

    Returns the evidence record ready to be stored in the execution log.
    """
    tool = action_result.get("tool", "unknown")
    status = action_result.get("status", "unknown")
    result_text = action_result.get("result", "")
    error = action_result.get("error", "")
    elapsed = action_result.get("elapsed_ms", 0)

    # ponytail: evidence confidence by execution quality
    if status == "done" and not error:
        confidence = 0.85  # system-executed
        if elapsed < 500:
            confidence = 0.9  # fast execution = high confidence it actually ran
    elif status == "done" and error:
        confidence = 0.4  # completed with errors
    else:
        confidence = 0.0  # failed

    evidence = {
        "id": "exec_ev_" + uuid.uuid4().hex[:16],
        "tool": tool,
        "status": status,
        "result": (result_text or "")[:2000],
        "error": error[:500] if error else None,
        "elapsed_ms": elapsed,
        "confidence": confidence,
        "executed_at": action_result.get("executed_at", now_iso()),
        "retries": action_result.get("retries", 0),
        "thread_id": thread_id,
        "decision_id": decision_id,
        "user_id": user_id,
        "org_id": org_id,
        "executive_id": executive_id,
    }

    log.info(f"execution collected: {tool} -> {status} (confidence {confidence})")
    return evidence


# Aggregate evidence into verification summary
def execution_summary(evidence_records: list) -> dict:
    """Aggregate summary for the Verification Engine and Cockpit."""
    total = len(evidence_records)
    if not total:
        return {"total": 0, "done": 0, "failed": 0, "avg_confidence": 0, "total_elapsed_ms": 0}

    done = sum(1 for e in evidence_records if e["status"] == "done")
    failed = sum(1 for e in evidence_records if e["status"] in ("failed", "skipped"))
    avg_conf = round(sum(e["confidence"] for e in evidence_records) / total, 2)
    total_elapsed = sum(e.get("elapsed_ms", 0) for e in evidence_records)

    return {
        "total": total,
        "done": done,
        "failed": failed,
        "completion_pct": round(100 * done / total) if total else 0,
        "avg_confidence": avg_conf,
        "total_elapsed_ms": total_elapsed,
        "tools_used": list(set(e["tool"] for e in evidence_records)),
        "verdict": "success" if done == total else ("partial" if done > 0 else "failed"),
    }


# ponytail: verification hooks — these will be called by decision_brain
# after outcomes are reviewed to close the feedback loop.
def verification_feed(evidence: dict, predicted_outcome: dict, actual_outcome: dict) -> dict:
    """Compare prediction vs actual after execution evidence comes in.
    Returns calibration update for the decision ledger."""
    pred_claim = predicted_outcome.get("claim", "")
    pred_conf = predicted_outcome.get("confidence", 50)
    actual_status = actual_outcome.get("status", "unknown")

    # ponytail: simple match — if evidence shows tool ran successfully
    # and the predicted outcome was positive, we have a match.
    evidence_status = evidence.get("status", "")
    evidence_conf = evidence.get("confidence", 0)

    matched = (evidence_status == "done" and actual_status in ("success", "partial"))
    gap = pred_conf - (100 if matched else 0)

    return {
        "predicted": pred_claim[:200],
        "predicted_confidence": pred_conf,
        "actual_status": actual_status,
        "evidence_confidence": evidence_conf,
        "matched": matched,
        "calibration_gap": gap,
        "note": "overconfident" if gap > 15 else ("underconfident" if gap < -15 else "calibrated"),
    }
