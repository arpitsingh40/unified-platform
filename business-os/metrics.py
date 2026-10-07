"""Business Metrics — Phase 1 business sensing.

Ingests metrics from manual entry and connected toolkits (Stripe),
computes an org-level financial snapshot (cash, runway, MRR, churn, CAC),
and raises warn/crit flags that feed SALAAR threat detection.

A daemon-friendly background job re-pulls metrics for every org every 6 hours.
"""
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from db import _col, orgs_col

log = logging.getLogger("metrics")

# Metrics and alert collection handles (None when no DB configured)
org_metrics_col = _col("org_metrics")
metric_alerts_col = _col("metric_alerts")

# Background job cadence: run every 6 hours, check stop flag every 60s
METRICS_INTERVAL_S = 6 * 3600
SLEEP_CHUNK_S = 60

# Module-level stop flag checked by the background loop
_stop_flag = threading.Event()

# Idempotency guard for ensure_metrics_startup
_started = False


# Coerce a metric doc's value to float (0.0 when missing or unparsable)
def _num(doc):
    if not doc:
        return 0.0
    try:
        return float(doc.get("value", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


# Latest metric doc per name for an org (newest ts wins)
def _latest_metrics(org_id):
    out = {}
    if org_metrics_col is None:
        return out
    for doc in org_metrics_col.find({"org_id": org_id}).sort("ts", -1):
        name = doc.get("name")
        if name and name not in out:
            out[name] = doc
    return out


# True when the last three MRR ingestions are strictly declining
def _mrr_declining(mrr_doc):
    if not mrr_doc:
        return False
    hist = [h.get("value") for h in mrr_doc.get("history", []) if isinstance(h, dict)]
    if len(hist) < 3:
        return False
    a, b, c = hist[-3], hist[-2], hist[-1]
    return a > b > c


# Parse the stripe handler's formatted invoice lines into (amount, status) dicts
def _parse_stripe_invoices(result_text):
    invoices = []
    if not result_text:
        return invoices
    for line in result_text.splitlines():
        m = re.match(r"-\s*\S+:\s*\$?([\d.]+)\s*\((\w+)\)", line.strip())
        if not m:
            continue
        try:
            invoices.append({"amount": float(m.group(1)), "status": m.group(2).lower()})
        except ValueError:
            continue
    return invoices


def ingest_metric(org_id, name, value, source="manual"):
    """Store the latest value for (org_id, name). Returns the record id."""
    if org_metrics_col is None:
        return None
    ts = datetime.now(timezone.utc)
    existing = org_metrics_col.find_one({"org_id": org_id, "name": name})
    if existing:
        history = (existing.get("history") or [])[-29:] + [{"value": value, "ts": ts, "source": source}]
        org_metrics_col.update_one({"id": existing["id"]}, {"$set": {
            "value": value, "ts": ts, "source": source,
            "history": history, "updated_at": ts,
        }})
        return existing["id"]
    doc = {
        "id": str(uuid.uuid4()), "org_id": org_id, "name": name,
        "value": value, "source": source, "ts": ts,
        "created_at": ts, "updated_at": ts,
        "history": [{"value": value, "ts": ts, "source": source}],
    }
    org_metrics_col.insert_one(doc)
    return doc["id"]


def pull_stripe_metrics(org_id):
    """List invoices via the stripe handler, compute mrr/receivables/overdue, ingest them.
    Degrades gracefully: returns {"connected": False} when Stripe is unavailable."""
    try:
        from execution.handlers.stripe import handle as stripe_handle
        res = stripe_handle("STRIPE_LIST_INVOICES", {"limit": 100})
    except Exception as e:
        log.warning("metrics: stripe handler unavailable for org %s: %s", org_id, e)
        return {"connected": False}
    if not res.get("successful"):
        return {"connected": False, "reason": str(res.get("error", "stripe unavailable"))[:200]}
    invoices = _parse_stripe_invoices(res.get("result", ""))
    mrr = sum(i["amount"] for i in invoices if i["status"] == "paid")
    receivables = sum(i["amount"] for i in invoices if i["status"] == "open")
    # Handler output carries no due dates, so overdue is proxied by open invoice count
    overdue = sum(1 for i in invoices if i["status"] == "open")
    ingest_metric(org_id, "mrr", round(mrr, 2), source="stripe")
    ingest_metric(org_id, "receivables", round(receivables, 2), source="stripe")
    ingest_metric(org_id, "overdue_invoices", float(overdue), source="stripe")
    return {"connected": True, "mrr": round(mrr, 2), "receivables": round(receivables, 2), "overdue": overdue}


def compute_org_snapshot(org_id):
    """Read recent metrics and return snapshot dict with rule-driven flags."""
    m = _latest_metrics(org_id)
    cash = _num(m.get("cash"))
    burn = max(_num(m.get("expenses")), 0.0)
    runway_days = round(cash / burn, 1) if burn > 0 else None
    mrr = _num(m.get("mrr"))
    churn_pct = _num(m.get("churn_pct"))
    cac = _num(m.get("cac"))
    payback_months = round(cac / mrr, 1) if mrr > 0 else None
    receivables = _num(m.get("receivables"))
    payables = _num(m.get("payables"))
    flags = []
    if runway_days is not None and runway_days < 60:
        flags.append({"key": "runway", "level": "crit", "message": "Runway below 60 days"})
    if mrr > 0 and receivables > 2 * mrr:
        flags.append({"key": "receivables", "level": "warn", "message": "Receivables exceed 2x MRR"})
    if _mrr_declining(m.get("mrr")):
        flags.append({"key": "mrr_decline", "level": "warn", "message": "MRR declining for 2 consecutive ingestions"})
    if churn_pct > 5:
        flags.append({"key": "churn", "level": "crit", "message": "Churn above 5%"})
    return {
        "org_id": org_id,
        "cash": cash,
        "runway_days": runway_days,
        "mrr": mrr,
        "churn_pct": churn_pct,
        "cac": cac,
        "payback_months": payback_months,
        "receivables": receivables,
        "payables": payables,
        "as_of": datetime.now(timezone.utc),
        "flags": flags,
    }


# Map a metric flag key to a SALAAR threat key
FLAG_THREAT_MAP = {
    "runway": "cash_crisis",
    "receivables": "cash_crisis",
    "mrr_decline": "cash_crisis",
    "churn": "customer_churn_signal",
}


def evaluate_metric_alerts(org_id):
    """Store open alerts for warn/crit flags and call salaar.record_threat."""
    snap = compute_org_snapshot(org_id)
    created = []
    for flag in snap.get("flags", []):
        if flag["level"] not in ("warn", "crit"):
            continue
        if metric_alerts_col is not None:
            # Dedupe: refresh last_seen instead of re-inserting an open alert
            existing = metric_alerts_col.find_one({"org_id": org_id, "key": flag["key"], "status": "open"})
            if existing:
                metric_alerts_col.update_one({"id": existing["id"]}, {"$set": {
                    "last_seen": datetime.now(timezone.utc),
                }})
                continue
            aid = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            metric_alerts_col.insert_one({
                "id": aid, "org_id": org_id, "key": flag["key"], "level": flag["level"],
                "message": flag["message"], "status": "open",
                "created_at": now, "last_seen": now, "resolved_at": None,
            })
            created.append({"id": aid, "key": flag["key"], "level": flag["level"], "message": flag["message"]})
        # SALAAR shadow agent sees the alert through record_threat
        try:
            from salaar.threats import record_threat, THREAT_RULES
            threat_key = FLAG_THREAT_MAP.get(flag["key"], "cash_crisis")
            rule = THREAT_RULES.get(threat_key, {})
            record_threat(
                org_id, threat_key, "system", flag["message"],
                rule.get("severity", "critical" if flag["level"] == "crit" else "high"),
                rule.get("lenses", []), rule.get("diagnosis", flag["message"]),
            )
        except Exception as e:
            log.warning("metrics: salaar record_threat failed for org %s: %s", org_id, e)
    return created


# One metrics pass over every organization (stripe → snapshot → alerts)
def _run_metrics_cycle():
    if orgs_col is None:
        log.warning("metrics: db unavailable, skipping cycle")
        return
    for org in orgs_col.find({}, {"id": 1}):
        org_id = org.get("id")
        if not org_id:
            continue
        try:
            pull_stripe_metrics(org_id)
            compute_org_snapshot(org_id)
            evaluate_metric_alerts(org_id)
        except Exception as e:
            log.warning("metrics: org %s failed: %s", org_id, e)


def run_metrics_jobs():
    """Forever loop: run a metrics pass per org every 6 hours until the stop flag is set."""
    log.info("metrics jobs started (interval=%ss)", METRICS_INTERVAL_S)
    while not _stop_flag.is_set():
        try:
            _run_metrics_cycle()
        except Exception as e:
            log.warning("metrics: cycle crashed: %s", e)
        elapsed = 0.0
        while elapsed < METRICS_INTERVAL_S and not _stop_flag.is_set():
            _stop_flag.wait(SLEEP_CHUNK_S)
            elapsed += SLEEP_CHUNK_S


def ensure_metrics_startup():
    """Index best-effort + start run_metrics_jobs in a daemon thread."""
    global _started
    if _started:
        return
    _started = True
    if org_metrics_col is not None:
        try:
            org_metrics_col.create_index([("org_id", 1), ("name", 1)])
        except Exception as e:
            log.warning("metrics: org_metrics index failed: %s", e)
    if metric_alerts_col is not None:
        try:
            metric_alerts_col.create_index([("org_id", 1), ("created_at", -1)])
        except Exception as e:
            log.warning("metrics: metric_alerts index failed: %s", e)
    threading.Thread(target=run_metrics_jobs, name="metrics-jobs", daemon=True).start()
    log.info("metrics background job started")
