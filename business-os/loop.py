"""Closed Decision→Action→Outcome Loop — Phase 2 of the automation platform.

Records decision outcomes, links Decision → ExecutionPlan → Evidence,
computes variance between predictions and actuals, and auto-generates
weekly loop reports. A daemon thread runs the weekly review once per day.
"""
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import db as db_module
from db import _col, orgs_col, evidence_col

log = logging.getLogger("loop")

# Loop ledger collections
decision_outcomes_col = _col("decision_outcomes")
loop_reports_col = _col("loop_reports")
org_metrics_col = _col("org_metrics")
salaar_chains_col = _col("salaar_chains")

# Daily run bookkeeping (in-process only; resets on restart)
_daily_state = {"last_run": None}

# Check the loop thread every 60s
LOOP_CHECK_SECONDS = 60

# Treat a run as "daily" after 23 hours
DAILY_INTERVAL_HOURS = 23


# Current UTC timestamp helper
def _now():
    return datetime.now(timezone.utc)


# Store a decision outcome doc (prediction vs actual) in the loop ledger
def record_decision_outcome(org_id, decision_id, prediction, actual, outcome, metrics_delta=None):
    if decision_outcomes_col is None:
        raise RuntimeError("decision_outcomes collection unavailable")
    doc = {
        "org_id": org_id,
        "decision_id": decision_id,
        "prediction": prediction,
        "actual": actual,
        "outcome": outcome,
        "metrics_delta": metrics_delta,
        "plan_id": None,
        "ts": _now(),
    }
    decision_outcomes_col.insert_one(doc)
    return doc


# Link an execution plan to its decision outcome doc (Decision → ExecutionPlan → Evidence)
def link_execution_to_decision(decision_id, plan_id):
    if decision_outcomes_col is None:
        return None
    exec_col = getattr(db_module, "execution_plans_col", None) or getattr(db_module, "plans_col", None)
    if exec_col is not None:
        try:
            exec_col.update_one({"id": plan_id}, {"$set": {"decision_id": decision_id}})
        except Exception as e:
            log.warning(f"loop: plan link failed for {plan_id}: {e}")
    res = decision_outcomes_col.update_one(
        {"decision_id": decision_id}, {"$set": {"plan_id": plan_id}})
    return {"decision_id": decision_id, "plan_id": plan_id, "linked": res.modified_count > 0}


# Gather open predictions from salaar chains, OKR targets, and pending decision outcomes
def collect_predictions(org_id):
    items = []
    if salaar_chains_col is not None:
        for chain in salaar_chains_col.find({"org_id": org_id, "type": "causal_chain", "status": "active"}):
            steps = chain.get("steps", [])
            current = chain.get("current_step", 1)
            step = next((s for s in steps if s.get("step") == current), None)
            items.append({
                "source": "salaar_chain",
                "item": chain.get("chain_name") or chain.get("id", "chain"),
                "predicted": (step or {}).get("predicted_response", ""),
                "confidence": chain.get("success_probability"),
                "metric": None,
                "target": None,
                "chain_id": chain.get("id"),
            })
    try:
        from okr_engine import get_all_department_krs
        for kr in get_all_department_krs(org_id):
            items.append({
                "source": "okr",
                "item": kr.get("description", ""),
                "predicted": kr.get("target"),
                "metric": kr.get("description", ""),
                "target": kr.get("target"),
                "current": kr.get("current"),
                "department": kr.get("department"),
            })
    except ImportError:
        pass
    if decision_outcomes_col is not None:
        for d in decision_outcomes_col.find({"org_id": org_id, "outcome": "pending"}).sort("ts", -1).limit(25):
            items.append({
                "source": "decision_outcome",
                "item": d.get("decision_id", ""),
                "predicted": d.get("prediction"),
                "metric": None,
                "target": None,
                "decision_id": d.get("decision_id"),
            })
    return items


# Fetch the latest stored value for a named org metric
def _latest_metric(org_id, name):
    if org_metrics_col is None or not name:
        return None
    doc = org_metrics_col.find_one({"org_id": org_id, "name": name}, sort=[("ts", -1)])
    if not doc:
        return None
    for key in ("value", "actual", "result"):
        if key in doc:
            return doc[key]
    return doc


# Latest evidence outcome for an org (fallback when no metric is stored)
def _latest_evidence_status(org_id):
    if evidence_col is None:
        return None
    ev = evidence_col.find_one({"org_id": org_id, "outcome": {"$exists": True}},
                                sort=[("timestamp", -1)])
    return ev.get("outcome") if ev else None


# Compute variance for every open prediction against actual metrics or evidence
def compute_variance(org_id):
    variances = []
    for item in collect_predictions(org_id):
        predicted = item.get("predicted")
        actual = _latest_metric(org_id, item.get("metric")) if item.get("metric") else None
        if actual is None and item.get("source") == "okr":
            actual = item.get("current")
        flag = "unknown"
        delta = None
        if actual is None and item.get("source") == "salaar_chain":
            ev = _latest_evidence_status(org_id)
            if ev:
                actual = ev
                delta = 1 if ev == "SUCCESS" else (0.5 if ev == "PARTIAL" else 0)
                flag = "on_track" if ev == "SUCCESS" else "off_track"
        elif actual is not None and predicted is not None:
            try:
                if isinstance(actual, (int, float)) and isinstance(predicted, (int, float)):
                    delta = float(actual) - float(predicted)
                    flag = "on_track" if delta >= 0 else "off_track"
                else:
                    flag = "unknown"
            except (TypeError, ValueError):
                flag = "unknown"
        variances.append({
            "item": item.get("item", ""),
            "source": item.get("source", ""),
            "predicted": predicted,
            "actual": actual,
            "delta": delta,
            "flag": flag,
        })
    return variances


# Build a deterministic plain-text narrative from variances
def _build_summary(variances):
    n = len(variances)
    if n == 0:
        return "No open predictions to review this week."
    on = sum(1 for v in variances if v.get("flag") == "on_track")
    off = sum(1 for v in variances if v.get("flag") == "off_track")
    unk = sum(1 for v in variances if v.get("flag") == "unknown")
    parts = [f"This week the loop tracked {n} open predictions: {on} on track, "
             f"{off} off track, and {unk} unknown."]
    if off:
        names = [v["item"] for v in variances if v.get("flag") == "off_track"][:3]
        parts.append("Priority items needing attention: " + ", ".join(names) + ".")
    elif unk:
        names = [v["item"] for v in variances if v.get("flag") == "unknown"][:3]
        parts.append("Items still awaiting measurable outcomes: " + ", ".join(names) + ".")
    return " ".join(parts)


# Assemble and persist the weekly closed-loop report for one org
def generate_weekly_auto_review(org_id):
    predictions = collect_predictions(org_id)
    variances = compute_variance(org_id)
    actuals = [{"item": v["item"], "actual": v["actual"]}
               for v in variances if v.get("actual") is not None]
    alerts = [{"item": v["item"], "flag": v["flag"], "predicted": v["predicted"],
               "actual": v["actual"], "delta": v["delta"]}
              for v in variances if v.get("flag") in ("off_track", "unknown")]
    now = _now()
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    report = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "week_start": week_start,
        "predictions": predictions,
        "actuals": actuals,
        "variances": variances,
        "summary": _build_summary(variances),
        "alerts": alerts,
        "generated_at": now,
    }
    if loop_reports_col is not None:
        loop_reports_col.insert_one(report)
    return report


# Run the weekly auto-review once per day for every org
def _run_daily_loop():
    now = _now()
    last = _daily_state["last_run"]
    if last and (now - last) < timedelta(hours=DAILY_INTERVAL_HOURS):
        return
    _daily_state["last_run"] = now
    if orgs_col is None:
        return
    for org in orgs_col.find({}, {"_id": 0, "id": 1}):
        try:
            generate_weekly_auto_review(org["id"])
        except Exception as e:
            log.warning(f"loop: weekly auto-review failed for org {org.get('id')}: {e}")


# Daemon thread: checks every 60s, runs the daily loop review for all orgs
def ensure_loop_startup():
    if not os.environ.get("MONGO_URL"):
        log.info("loop: MONGO_URL not set — daemon skipped")
        return None

    def _worker():
        while True:
            try:
                _run_daily_loop()
            except Exception as e:
                log.warning(f"loop: daily worker error: {e}")
            time.sleep(LOOP_CHECK_SECONDS)

    t = threading.Thread(target=_worker, daemon=True, name="loop-weekly-review")
    t.start()
    log.info("loop: weekly auto-review daemon started")
    return t
