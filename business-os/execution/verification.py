"""
Verification + Learning Runtime.

Verification: Did the executed action achieve the intended capability outcome?
LLM-powered deep verification with keyword fallback for reliability.

Learning: Update tool scores, detect patterns, apply only verified evidence.

Evidence-first learning. No permanent organizational learning without verification.
Evidence and learning events persist in MongoDB (evidence / learning_events collections)
— this ledger is the proof engine and must survive restarts.
"""

import json
import logging
from collections import defaultdict
from typing import Optional

from ontology import (
    Evidence, LearningEvent, LearningImpact,
    OutcomeStatus, Volatility, new_id, utcnow,
)
from db import evidence_col, learning_col

log = logging.getLogger("execution.verification")

# Lightweight LLM call for deep verification — uses DeepSeek v4 Flash for speed/cost
VERIFY_SYSTEM = """You assess whether a tool execution achieved its goal. Compare expected outcome to actual result.

Output ONLY valid JSON:
{"outcome": "SUCCESS"|"FAILURE"|"PARTIAL"|"UNKNOWN",
 "confidence": 0.0 to 1.0,
 "reasoning": "one line explaining why",
 "systemic_flag": true if this looks like a systemic issue (bad config, expired auth, broken integration) not a one-off}"""

# Model used for deep verification calls
VERIFY_MODEL = "deepseek-v4-flash"


def _llm_verify(tool_slug: str, expected: str, actual: str) -> dict:
    """Deep verification: one LLM call with DeepSeek v4 Flash.
    Falls back to keyword heuristic on any failure."""
    try:
        from llm_client import client as llm_client, _extract_json
        prompt = (
            f"TOOL: {tool_slug}\n"
            f"EXPECTED: {expected}\n"
            f"ACTUAL RESULT:\n{actual[:2000]}"
        )
        r = llm_client().messages.create(
            model=VERIFY_MODEL, max_tokens=200,
            system=[{"type": "text", "text": VERIFY_SYSTEM}],
            messages=[{"role": "user", "content": prompt}],
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        result = json.loads(_extract_json(txt))
        result["source"] = "llm"
        return result
    except Exception as e:
        log.warning(f"LLM verification failed, falling back to keyword: {e}")
        return None


def _keyword_verify(actual: str) -> dict:
    """Keyword heuristic fallback — fast, cheap, zero-LLM."""
    result_lower = (actual or "").lower().strip()
    failure_signals = ["error", "failed", "denied", "unauthorized", "timeout", "not found",
                       "could not", "unable", "refused", "blocked", "exception", "traceback"]
    success_signals = ["sent", "created", "delivered", "scheduled", "completed", "ok",
                       "success", "done", "received", "resolved", "processed", "confirmed"]

    is_failure = any(s in result_lower for s in failure_signals)
    is_success = any(s in result_lower for s in success_signals) and not is_failure

    if is_failure:
        return {"outcome": "FAILURE", "confidence": 0.3, "reasoning": "Keyword failure signal detected", "source": "keyword"}
    elif is_success:
        return {"outcome": "SUCCESS", "confidence": 0.7, "reasoning": "Keyword success signal detected", "source": "keyword"}
    elif len(actual) > 5:
        return {"outcome": "PARTIAL", "confidence": 0.4, "reasoning": "Result present but unclear outcome", "source": "keyword"}
    else:
        return {"outcome": "UNKNOWN", "confidence": 0.1, "reasoning": "Empty or garbled result", "source": "keyword"}


def verify_action(
    tool_slug: str,
    capability: str,
    expected_outcome: str,
    actual_result: str,
    trace_id: str = None,
    executive_id: str = None,
    org_id: str = None,
    deep_verify: bool = True,
) -> Evidence:
    """Compare expected vs actual outcome and produce verified evidence.
    deep_verify=True: uses LLM for deep assessment, falls back to keyword heuristic.
    deep_verify=False: keyword heuristic only (cheaper, used for batch verification)."""
    actual = actual_result or ""

    verdict = None
    if deep_verify:
        verdict = _llm_verify(tool_slug, expected_outcome, actual)

    if verdict is None:
        verdict = _keyword_verify(actual)

    outcome_str = verdict.get("outcome", "UNKNOWN")
    confidence = float(verdict.get("confidence", 0.1))
    reasoning = verdict.get("reasoning", "")

    # Map to OutcomeStatus enum
    outcome_map = {
        "SUCCESS": OutcomeStatus.SUCCESS,
        "FAILURE": OutcomeStatus.FAILURE,
        "PARTIAL": OutcomeStatus.PARTIAL,
        "UNKNOWN": OutcomeStatus.UNKNOWN,
    }
    outcome = outcome_map.get(outcome_str, OutcomeStatus.UNKNOWN)

    # Adjust confidence: keyword gets a penalty
    if verdict.get("source") == "keyword":
        confidence = min(confidence, 0.75)
    elif verdict.get("source") == "llm":
        confidence = max(confidence, 0.5)  # LLM assessments floor at 0.5

    ev = Evidence(
        trace_id=trace_id,
        evidence_type="EXECUTION",
        outcome=outcome,
        expected_outcome=expected_outcome,
        actual_result=actual_result,
        confidence=confidence,
        timestamp=utcnow(),
        volatility=Volatility.STABLE,
    )

    doc = ev.model_dump()
    doc["tool_slug"] = tool_slug
    doc["capability"] = capability
    doc["executive_id"] = executive_id
    doc["org_id"] = org_id
    doc["verification_method"] = verdict.get("source", "keyword")
    doc["verification_reasoning"] = reasoning
    doc["systemic_flag"] = bool(verdict.get("systemic_flag", False))

    if evidence_col is not None:
        try:
            evidence_col.insert_one(dict(doc))
        except Exception as e:
            log.error(f"Evidence persist failed: {e}")

    verif_label = f"deep-LLM" if verdict.get("source") == "llm" else "keyword"
    log.info(f"Verification [{verif_label}]: {tool_slug} → {outcome_str} (confidence={confidence:.2f})")

    # Update tool scores
    try:
        from .tie import record_outcome as _tie_record
        _tie_record(tool_slug, outcome == OutcomeStatus.SUCCESS)
    except ImportError:
        pass

    return ev


def learn_from_evidence(evidence: Evidence, capability: str = "", org_id: str = None) -> Optional[LearningEvent]:
    """Detect patterns from verified evidence and produce learning.
    Now detects: 1) consecutive tool failures, 2) systemic integration issues flagged by LLM verification."""
    if evidence_col is None:
        return None
    q = {"outcome": {"$in": ["SUCCESS", "FAILURE", "PARTIAL"]}}
    if org_id:
        q["org_id"] = org_id
    recent = list(evidence_col.find(q, {"_id": 0}).sort("timestamp", -1).limit(50))

    if len(recent) < 3:
        return None

    # Pattern 1: consecutive failures of same tool
    tool_failures = defaultdict(list)
    for e in recent:
        slug = e.get("tool_slug", "unknown")
        if e.get("outcome") == "FAILURE":
            tool_failures[slug].append(e)

    learn = None
    for slug, failures in tool_failures.items():
        if len(failures) >= 3:
            already = learning_col is not None and learning_col.find_one(
                {"pattern_key": f"fail_{slug}", "org_id": org_id})
            if not already:
                # Enhanced: if LLM flagged any as systemic, note it
                systemic = any(f.get("systemic_flag") for f in failures)
                pattern = f"Tool {slug} failed {len(failures)} times in recent executions"
                if systemic:
                    pattern += " [SYSTEMIC: likely integration/auth/config issue, not a one-off]"
                learn = LearningEvent(
                    derived_from=[f.get("id", "") for f in failures],
                    pattern=pattern,
                    impact=LearningImpact.TOOL_SCORE,
                    applied=True,
                    applied_at=utcnow(),
                )
                if learning_col is not None:
                    row = learn.model_dump()
                    row["pattern_key"] = f"fail_{slug}"
                    row["org_id"] = org_id
                    row["systemic"] = systemic
                    learning_col.insert_one(row)
                log.warning(f"Learning: {learn.pattern}")
                break

    # Pattern 2: systemic flags across different tools — suggests broader infra issue
    systemic_flags = [e for e in recent if e.get("systemic_flag")]
    if len(systemic_flags) >= 2:
        tools = list(set(e.get("tool_slug", "") for e in systemic_flags))
        already = learning_col is not None and learning_col.find_one(
            {"pattern_key": "systemic_cross_tool", "org_id": org_id})
        if not already:
            learn2 = LearningEvent(
                derived_from=[e.get("id", "") for e in systemic_flags],
                pattern=f"Cross-tool systemic issue detected: {', '.join(tools[:3])} — possible infra/auth/config root cause",
                impact=LearningImpact.TOOL_SCORE,
                applied=True,
                applied_at=utcnow(),
            )
            if learning_col is not None:
                row2 = learn2.model_dump()
                row2["pattern_key"] = "systemic_cross_tool"
                row2["org_id"] = org_id
                row2["systemic"] = True
                learning_col.insert_one(row2)
            log.warning(f"Learning: {learn2.pattern}")

    return learn


def get_tool_reliability(tool_slug: str) -> dict:
    """Get reliability stats for a tool."""
    try:
        from .tie import _tool_scores
        if tool_slug in _tool_scores:
            s = _tool_scores[tool_slug]
            total = s["success"] + s["failure"]
            return {
                "tool": tool_slug,
                "success": s["success"],
                "failure": s["failure"],
                "total": total,
                "reliability": round(s["success"] / total, 2) if total > 0 else 0.5,
                "avg_latency_ms": s.get("avg_latency_ms", 0),
            }
    except ImportError:
        pass
    return {"tool": tool_slug, "reliability": 0.5, "note": "cold_start"}


def learning_summary(org_id: str = None) -> dict:
    """Summary of all organizational learning."""
    if evidence_col is None or learning_col is None:
        return {"total_evidence": 0, "total_learning_events": 0, "recent_learnings": []}
    q = {"org_id": org_id} if org_id else {}
    recents = list(learning_col.find(q, {"_id": 0, "pattern": 1}).sort("applied_at", -1).limit(10))
    return {
        "total_evidence": evidence_col.count_documents(q),
        "total_learning_events": learning_col.count_documents(q),
        "recent_learnings": [l.get("pattern", "") for l in recents],
    }


# ── Demo ──
def _demo():
    ev = verify_action("GMAIL_SEND_EMAIL", "email",
                       "Email delivered to customer",
                       "Email sent successfully, opened in 12 minutes",
                       trace_id="trace_abc", org_id="org_demo")
    ev2 = verify_action("GMAIL_SEND_EMAIL", "email",
                        "Email delivered", "Error: connection refused",
                        trace_id="trace_def", org_id="org_demo")
    ev3 = verify_action("GMAIL_SEND_EMAIL", "email",
                        "Email delivered", "Error: timeout",
                        trace_id="trace_ghi", org_id="org_demo")
    ev4 = verify_action("GMAIL_SEND_EMAIL", "email",
                        "Email delivered", "Error: quota exceeded... failed",
                        trace_id="trace_jkl", org_id="org_demo")

    assert ev.outcome == OutcomeStatus.SUCCESS
    assert ev2.outcome == OutcomeStatus.FAILURE
    learn = learn_from_evidence(ev4, "email", org_id="org_demo")
    assert learn is not None and "failed" in learn.pattern, "3 failures must produce a learning event"
    reliability = get_tool_reliability("GMAIL_SEND_EMAIL")
    summary = learning_summary("org_demo")
    assert summary["total_evidence"] >= 4

    return {
        "evidence_count": summary["total_evidence"],
        "learning_events": summary["total_learning_events"],
        "reliability": reliability,
        "summary": summary,
        "status": "OK",
    }


if __name__ == "__main__":
    print(json.dumps(_demo(), indent=2, default=str))
