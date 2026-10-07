"""Phase 3 — Three end-to-end automation loops (cash, customer, team).

Each loop is a synchronous, deterministic pipeline:
  cash     — Stripe invoices → overdue detection → Gmail reminders → org_metrics → founder task
  customer — org_metrics (mrr trend, churn_pct) → churn-risk score → re-engagement tasks/emails
  team     — GitHub issues → stale-task detection → OKR check-in tasks for lagging goals

Governance contract: governance.py (same dir) exposes kill_switch_active() / dry_run_enabled().
If it is missing, env vars KILL_SWITCH=1 / DRY_RUN=1 act as fallbacks.
"""

import os
import re
import time
import logging
import threading
from datetime import datetime, timezone, timedelta

from db import _col, orgs_col, users_col
from ontology.models import new_id, utcnow

log = logging.getLogger("automation_loops")

# Governance dependency contract — real module wins, env fallback otherwise
try:
    from governance import kill_switch_active, dry_run_enabled
except ImportError:
    def kill_switch_active():
        return os.environ.get("KILL_SWITCH", "").strip() == "1"

    def dry_run_enabled():
        return os.environ.get("DRY_RUN", "").strip() == "1"

# Collection handles (automation_runs logs every loop execution)
automation_runs_col = _col("automation_runs")
org_metrics_col = _col("org_metrics")
exec_tasks_coll = _col("exec_tasks")          # pending/approved tasks for staleness checks

# Scheduler state
_STOP_FLAG = threading.Event()
_SCHEDULER_STARTED = False
LOOP_INTERVAL_SECONDS = 12 * 60 * 60          # run all loops every 12 hours
STALE_TASK_DAYS = 14                          # pending tasks older than this are "stale"


# Current UTC timestamp as ISO string
def _now_iso():
    return utcnow().isoformat()


# Kill switch may raise if governance is broken — never let it crash a loop
def _is_killed():
    try:
        return bool(kill_switch_active())
    except Exception as e:
        log.error("governance.kill_switch_active failed: %s", e)
        return False


# Dry-run flag — safe fallback to False if governance misbehaves
def _is_dry_run():
    try:
        return bool(dry_run_enabled())
    except Exception as e:
        log.error("governance.dry_run_enabled failed: %s", e)
        return False


# True only when real external actions are allowed (not killed, not dry-run)
def _gated(org_id):
    return (not _is_killed()) and (not _is_dry_run())


# Build one step record
def _step(name, status, detail=""):
    return {"step": name, "status": status, "detail": str(detail)[:500]}


# Persist one automation run document. Returns run id or None (DB absent).
def _record_run(org_id, loop_name, steps, dry_run):
    if automation_runs_col is None:
        return None
    doc = {
        "id": new_id("arun_"),
        "org_id": org_id,
        "loop": loop_name,
        "dry_run": bool(dry_run),
        "ts": _now_iso(),
        "steps": steps,
    }
    automation_runs_col.insert_one(doc)
    return doc["id"]


# Call the native Stripe handler (reused verbatim from execution/handlers/stripe.py)
def _stripe_handler_call():
    try:
        from execution.handlers import get_handler
        fn = get_handler("STRIPE_LIST_INVOICES")
        if fn is None:
            return {"error": "no native stripe handler registered", "successful": False}
        return fn("STRIPE_LIST_INVOICES", {"limit": 100})
    except Exception as e:
        return {"error": str(e)[:300], "successful": False}


# Raw structured open invoices — the handler returns display text only, so due dates
# and customer emails need one direct call (same STRIPE_API_KEY, same API).
def _stripe_raw_open_invoices(limit=100):
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key:
        return None
    try:
        import requests
        r = requests.get(
            "https://api.stripe.com/v1/invoices",
            auth=(key, ""),
            params={"limit": min(limit, 100), "status": "open"},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        return r.json().get("data", [])
    except Exception as e:
        log.warning("stripe raw fetch failed: %s", e)
        return None


# Send one email through the native Gmail handler
def _send_gmail(to_email, subject, body):
    from execution.handlers import get_handler
    fn = get_handler("GMAIL_SEND_EMAIL")
    if fn is None:
        raise RuntimeError("no native gmail handler registered")
    res = fn("GMAIL_SEND_EMAIL", {"to": to_email, "subject": subject, "body": body})
    if not res.get("successful"):
        raise RuntimeError(res.get("error", "gmail send failed"))
    return res


# Create a founder-visible task via the execution task engine (system executive)
def _enqueue_founder_task(org_id, task_data):
    from execution.tasks import enqueue_task
    return enqueue_task("system", task_data, org_id=org_id, trace_id=f"autoloop_{new_id()}")


# Owner email of the org (used for founder-brief emails)
def _founder_email(org_id):
    if orgs_col is None or users_col is None:
        return ""
    org = orgs_col.find_one({"id": org_id})
    if not org:
        return ""
    u = users_col.find_one({"id": org.get("owner_user_id")})
    return (u or {}).get("email", "")


# Parse an ISO timestamp into aware UTC datetime (or None)
def _parse_iso(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


# ── Cash loop ──────────────────────────────────────────────────────────

def run_cash_loop(org_id):
    """Pull open Stripe invoices, remind overdue customers, report receivables."""
    steps = []
    dry_run = _is_dry_run()
    allowed = _gated(org_id)

    # Kill switch: record and bail without touching any connector
    if _is_killed():
        steps.append(_step("gated", "skipped", "kill switch active"))
        _record_run(org_id, "cash", steps, dry_run)
        return {"loop": "cash", "steps": steps, "overdue_total": 0.0}

    # Step 1: list invoices through the native Stripe handler
    handler_result = _stripe_handler_call()
    if handler_result.get("successful"):
        steps.append(_step("list_invoices", "ok", handler_result.get("result", "")))
    else:
        steps.append(_step("list_invoices", "skipped", handler_result.get("error", "stripe handler unavailable")))

    # Step 2: structured invoice data for due-date math
    invoices = _stripe_raw_open_invoices() or []
    if invoices:
        now_ts = time.time()
        overdue = [i for i in invoices
                   if i.get("status") == "open" and i.get("due_date") and float(i["due_date"]) < now_ts]
        steps.append(_step("fetch_invoice_details", "ok", f"{len(invoices)} open, {len(overdue)} overdue"))
    else:
        overdue = []
        steps.append(_step("fetch_invoice_details", "skipped", "STRIPE_API_KEY not configured or API unreachable"))

    # Step 3: reminder emails per overdue invoice (skipped in dry-run)
    for inv in overdue[:20]:
        number = inv.get("number") or "unknown"
        email = inv.get("customer_email") or ""
        if not email:
            steps.append(_step(f"reminder:{number}", "skipped", "no customer email on invoice"))
            continue
        if allowed:
            try:
                amount = float(inv.get("amount_due", 0)) / 100.0
                _send_gmail(
                    email,
                    f"Payment reminder: invoice {number}",
                    f"Hello,\n\nInvoice {number} for ${amount:.2f} is past due. "
                    "Please settle it at your earliest convenience.\n\nThank you.",
                )
                steps.append(_step(f"reminder:{number}", "ok", f"reminder sent to {email}"))
            except Exception as e:
                steps.append(_step(f"reminder:{number}", "error", str(e)[:300]))
        else:
            steps.append(_step(f"reminder:{number}", "dry_run", f"would send reminder to {email}"))

    # Step 4: ingest total overdue into org_metrics as receivables_overdue
    overdue_total = round(sum(float(i.get("amount_due", 0)) / 100.0 for i in overdue), 2)
    if org_metrics_col is not None:
        org_metrics_col.insert_one({
            "id": new_id("met_"),
            "org_id": org_id,
            "metric": "receivables_overdue",
            "value": overdue_total,
            "ts": _now_iso(),
        })
        steps.append(_step("ingest_metric", "ok", f"receivables_overdue={overdue_total}"))
    else:
        steps.append(_step("ingest_metric", "skipped", "org_metrics collection unavailable"))

    # Step 5: founder-visible review task when anything is overdue
    if overdue:
        try:
            tid = _enqueue_founder_task(org_id, {
                "description": "Review overdue invoices",
                "capability": "finance",
                "expected_outcome": f"Collection plan for {len(overdue)} overdue invoice(s) totalling ${overdue_total}",
                "authority_required": "L3",
                "reversibility": "REVERSIBLE",
            })
            steps.append(_step("enqueue_review_task", "ok", f"task {tid} created"))
        except Exception as e:
            steps.append(_step("enqueue_review_task", "error", str(e)[:300]))
    else:
        steps.append(_step("enqueue_review_task", "skipped", "nothing overdue"))

    _record_run(org_id, "cash", steps, dry_run)
    return {"loop": "cash", "steps": steps, "overdue_total": overdue_total}


# ── Customer loop ──────────────────────────────────────────────────────

# Read recent org_metrics for the org: (churn_pct, mrr_trend_percent)
def _recent_customer_metrics(org_id, limit=50):
    if org_metrics_col is None:
        return None, 0.0
    rows = list(org_metrics_col.find({"org_id": org_id}).sort("ts", -1).limit(limit))
    if not rows:
        return None, 0.0
    churn = None
    mrr_vals = []
    for row in rows:
        if row.get("metric") == "churn_pct" and churn is None:
            churn = float(row.get("value", 0))
        if row.get("metric") in ("mrr", "mrr_trend"):
            mrr_vals.append(float(row.get("value", 0)))
    for row in rows:
        if "churn_pct" in row and churn is None:
            churn = float(row["churn_pct"])
        if "mrr" in row:
            mrr_vals.append(float(row["mrr"]))
    churn_pct = churn if churn is not None else 0.0
    mrr_trend = 0.0
    if len(mrr_vals) >= 2 and mrr_vals[-1]:
        mrr_trend = round((mrr_vals[0] - mrr_vals[-1]) / mrr_vals[-1] * 100.0, 2)
    return churn_pct, mrr_trend


# Deterministic 0-100 churn-risk score from churn % and MRR trend
def _churn_risk_score(churn_pct, mrr_trend):
    base = min(80.0, max(0.0, churn_pct) * 6.0)      # 13.3%+ churn alone maxes this term
    decline = max(0.0, -mrr_trend) * 4.0             # each -1% MRR trend adds 4 points
    return int(min(100, round(base + decline)))


def run_customer_loop(org_id):
    """Score churn risk from org metrics; enqueue re-engagement work when hot."""
    steps = []
    dry_run = _is_dry_run()
    allowed = _gated(org_id)

    # Kill switch: record and bail without touching any connector
    if _is_killed():
        steps.append(_step("gated", "skipped", "kill switch active"))
        _record_run(org_id, "customer", steps, dry_run)
        return {"loop": "customer", "steps": steps, "churn_risk": 0}

    # Step 1: read recent org metrics
    churn_pct, mrr_trend = _recent_customer_metrics(org_id)
    if churn_pct is None:
        steps.append(_step("read_metrics", "skipped", "no org_metrics rows for this org"))
        _record_run(org_id, "customer", steps, dry_run)
        return {"loop": "customer", "steps": steps, "churn_risk": 0}
    steps.append(_step("read_metrics", "ok", f"churn_pct={churn_pct}, mrr_trend={mrr_trend}%"))

    # Step 2: deterministic churn-risk score
    score = _churn_risk_score(churn_pct, mrr_trend)
    steps.append(_step("score", "ok", f"churn_risk={score}/100"))
    if score <= 60:
        steps.append(_step("reengage", "skipped", "churn risk below threshold"))
        _record_run(org_id, "customer", steps, dry_run)
        return {"loop": "customer", "steps": steps, "churn_risk": score}

    # Step 3: enqueue two re-engagement tasks
    for description in (
        "Re-engage at-risk customers: send personalized retention offers",
        "Schedule check-in calls with the 5 highest-churn-risk accounts",
    ):
        try:
            tid = _enqueue_founder_task(org_id, {
                "description": description,
                "capability": "customer_success",
                "expected_outcome": "Churn risk reduced below 60 within 14 days",
                "authority_required": "L3",
                "reversibility": "REVERSIBLE",
            })
            steps.append(_step("enqueue_reengage", "ok", f"task {tid}: {description[:60]}"))
        except Exception as e:
            steps.append(_step("enqueue_reengage", "error", str(e)[:300]))

    # Step 4: optional founder-brief email (external send — allowed mode only)
    owner_email = _founder_email(org_id)
    if owner_email:
        if allowed:
            try:
                _send_gmail(
                    owner_email,
                    f"Churn risk alert: {score}/100",
                    f"Churn risk score is {score}/100 (churn {churn_pct}%, MRR trend {mrr_trend}%). "
                    "Re-engagement tasks have been queued.",
                )
                steps.append(_step("founder_email", "ok", f"alert sent to {owner_email}"))
            except Exception as e:
                steps.append(_step("founder_email", "error", str(e)[:300]))
        else:
            steps.append(_step("founder_email", "dry_run", f"would alert {owner_email}"))
    else:
        steps.append(_step("founder_email", "skipped", "no owner email on record"))

    _record_run(org_id, "customer", steps, dry_run)
    return {"loop": "customer", "steps": steps, "churn_risk": score}


# ── Team loop ──────────────────────────────────────────────────────────

# GitHub repos configured for the org (org settings first, env default fallback)
def _org_github_repos(org_id):
    repos = []
    if orgs_col is not None:
        org = orgs_col.find_one({"id": org_id})
        if org:
            settings = org.get("settings") or {}
            repos = list(settings.get("github_repos") or org.get("github_repos") or [])
    if not repos:
        default = os.environ.get("GITHUB_DEFAULT_REPO", "").strip()
        if default:
            repos = [default]
    return [r for r in repos if r]


# Pending (proposed/approved) exec_tasks older than STALE_TASK_DAYS
def _stale_pending_tasks(org_id):
    if exec_tasks_coll is None:
        return []
    cutoff = utcnow() - timedelta(days=STALE_TASK_DAYS)
    stale = []
    for t in exec_tasks_coll.find(
        {"org_id": org_id, "status": {"$in": ["proposed", "approved"]}}, {"_id": 0}
    ):
        created = _parse_iso(t.get("created_at"))
        if created and created < cutoff:
            stale.append(t)
    return stale


# Deterministic OKR check-in summary: avg progress per goal (department+objective)
def _okr_checkin_summary(org_id):
    try:
        from okr_engine import get_all_department_krs
        krs = get_all_department_krs(org_id)
    except Exception as e:
        log.warning("okr_engine unavailable for org %s: %s", org_id, e)
        return {"goals": [], "total_krs": 0}
    goals = {}
    for kr in krs:
        objective = kr.get("objective") or kr.get("description") or "unnamed"
        key = f"{kr.get('department', 'general')}:{objective}"
        bucket = goals.setdefault(key, {"department": kr.get("department", "general"),
                                       "objective": objective, "progresses": []})
        bucket["progresses"].append(kr.get("progress", 0))
    out = []
    for key, bucket in goals.items():
        progresses = bucket["progresses"]
        out.append({
            "goal": key,
            "department": bucket["department"],
            "objective": bucket["objective"],
            "progress": round(sum(progresses) / len(progresses)),
            "kr_count": len(progresses),
        })
    return {"goals": out, "total_krs": len(krs)}


def run_team_loop(org_id):
    """Check GitHub issues, flag stale tasks, push OKR check-ins for lagging goals."""
    steps = []
    dry_run = _is_dry_run()
    allowed = _gated(org_id)

    # Kill switch: record and bail without touching any connector
    if _is_killed():
        steps.append(_step("gated", "skipped", "kill switch active"))
        _record_run(org_id, "team", steps, dry_run)
        return {"loop": "team", "steps": steps, "open_issues": 0, "okr_tasks_created": 0}

    # Step 1: open issues per configured repo via the native GitHub handler
    repos = _org_github_repos(org_id)
    total_issues = 0
    if not repos:
        steps.append(_step("github_issues", "skipped", "no github repos configured in org settings"))
    else:
        for repo in repos:
            try:
                from execution.handlers import get_handler
                fn = get_handler("GITHUB_LIST_ISSUES")
                if fn is None:
                    raise RuntimeError("no native github handler registered")
                res = fn("GITHUB_LIST_ISSUES", {"repo": repo, "state": "open"})
                if res.get("successful"):
                    n = len(re.findall(r"^- #\d+", res.get("result", ""), re.M))
                    total_issues += n
                    steps.append(_step(f"github_issues:{repo}", "ok", res.get("result", "")[:200]))
                else:
                    steps.append(_step(f"github_issues:{repo}", "skipped", res.get("error", "")[:200]))
            except Exception as e:
                steps.append(_step(f"github_issues:{repo}", "error", str(e)[:300]))

    # Step 2: flag stale pending exec_tasks
    stale = _stale_pending_tasks(org_id)
    if stale:
        detail = "; ".join((t.get("description") or "")[:60] for t in stale[:3])
        steps.append(_step("stale_tasks", "ok", f"{len(stale)} stale: {detail}"))
    else:
        steps.append(_step("stale_tasks", "ok", "0 stale pending tasks"))

    # Step 3: OKR check-in summary from okr_engine
    summary = _okr_checkin_summary(org_id)
    goals = summary.get("goals", [])
    steps.append(_step("okr_summary", "ok", f"{len(goals)} goal(s), {summary.get('total_krs', 0)} KR(s)"))

    # Step 4: one check-in task per goal under 50% progress
    created = 0
    for goal in goals:
        if goal.get("progress", 100) >= 50:
            continue
        try:
            tid = _enqueue_founder_task(org_id, {
                "description": f"OKR check-in: {goal.get('objective', 'unnamed')[:150]}",
                "capability": "general",
                "expected_outcome": f"Status update for '{goal.get('objective', '')[:100]}' "
                                   f"({goal.get('department', 'general')}) at {goal.get('progress')}% progress",
                "authority_required": "L3",
                "reversibility": "REVERSIBLE",
            })
            created += 1
            steps.append(_step("okr_task", "ok", f"task {tid} queued for {goal.get('objective', '')[:50]}"))
        except Exception as e:
            steps.append(_step("okr_task", "error", str(e)[:300]))
    if created == 0:
        steps.append(_step("okr_task", "skipped", "no goals below 50% progress"))

    _record_run(org_id, "team", steps, dry_run)
    return {"loop": "team", "steps": steps, "open_issues": total_issues, "okr_tasks_created": created}


# ── Combined runner ────────────────────────────────────────────────────

def run_all_loops(org_id):
    """Run cash, customer, team sequentially; return combined result."""
    results = {}
    for name, fn in (("cash", run_cash_loop), ("customer", run_customer_loop), ("team", run_team_loop)):
        try:
            results[name] = fn(org_id)
        except Exception as e:
            log.error("loop %s crashed for org %s: %s", name, org_id, e)
            results[name] = {"loop": name, "error": str(e)[:300],
                             "steps": [_step("loop", "error", str(e)[:300])]}

    # Merge steps in canonical order
    steps = []
    for name in ("cash", "customer", "team"):
        steps.extend(results.get(name, {}).get("steps", []))
    _record_run(org_id, "all", steps, _is_dry_run())
    return {"loop": "all", "runs": results, "steps": steps}


# Latest run documents for an org (newest first)
def latest_runs(org_id, limit=10):
    if automation_runs_col is None:
        return []
    return list(automation_runs_col.find({"org_id": org_id}, {"_id": 0}).sort("ts", -1).limit(limit))


# Count step statuses for one run document
def step_summary(run_doc):
    counts = {"ok": 0, "dry_run": 0, "skipped": 0, "error": 0}
    if not run_doc:
        return counts
    for s in run_doc.get("steps", []):
        status = s.get("status")
        if status in counts:
            counts[status] += 1
    return counts


# ── Scheduler ──────────────────────────────────────────────────────────

# All org ids in the workspace
def _all_org_ids():
    if orgs_col is None:
        return []
    try:
        return [o["id"] for o in orgs_col.find({}, {"id": 1}) if o.get("id")]
    except Exception as e:
        log.error("failed to list orgs: %s", e)
        return []


# Background loop: every 12h run all loops for every org; stop flag polled every 60s
def _scheduler_loop():
    next_run = time.time()
    while not _STOP_FLAG.is_set():
        _STOP_FLAG.wait(60)
        if _STOP_FLAG.is_set():
            break
        if time.time() < next_run:
            continue
        for org_id in _all_org_ids():
            if _STOP_FLAG.is_set():
                break
            try:
                run_all_loops(org_id)
            except Exception as e:
                log.error("automation loops failed for org %s: %s", org_id, e)
        next_run = time.time() + LOOP_INTERVAL_SECONDS


# Start the daemon scheduler thread (idempotent)
def ensure_automation_startup():
    global _SCHEDULER_STARTED
    if _SCHEDULER_STARTED:
        return
    _SCHEDULER_STARTED = True
    t = threading.Thread(target=_scheduler_loop, name="automation-loops", daemon=True)
    t.start()
    log.info("Automation loop scheduler started (every %ss)", LOOP_INTERVAL_SECONDS)
