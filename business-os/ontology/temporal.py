"""
Temporal Engine — time as a first-class dimension.

Every entity exists on a timeline. This module provides:
- Timestamp injection (utcnow with standard format)
- Freshness tracking (how old is this data?)
- Volatility tagging (how fast does this data change?)
- Decay functions for organizational memory
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional


# Data-change cadence bands used by decay logic.
class Volatility(str, Enum):
    STABLE = "STABLE"       # Changes yearly (org structure, mission)
    FLUID = "FLUID"         # Changes monthly (strategy, goals)
    VOLATILE = "VOLATILE"   # Changes daily/weekly (tasks, KPIs, tool scores)


# Current UTC timestamp for injection into entities.
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ISO 8601 string form of the current UTC time.
def iso_now() -> str:
    return utcnow().isoformat()


def age_days(timestamp: datetime) -> float:
    """How many days since this timestamp?"""
    return (utcnow() - timestamp).total_seconds() / 86400


# Hours elapsed since the given timestamp.
def age_hours(timestamp: datetime) -> float:
    return (utcnow() - timestamp).total_seconds() / 3600


def freshness_score(timestamp: datetime, volatility: Volatility = Volatility.STABLE) -> float:
    """0.0 (stale) to 1.0 (fresh). Decay depends on volatility."""
    days = age_days(timestamp)
    if volatility == Volatility.VOLATILE:
        return max(0.0, 1.0 - days / 3)     # decays over 3 days
    elif volatility == Volatility.FLUID:
        return max(0.0, 1.0 - days / 30)    # decays over 30 days
    else:
        return max(0.0, 1.0 - days / 365)   # decays over 1 year


def is_stale(timestamp: datetime, volatility: Volatility = Volatility.STABLE, threshold: float = 0.3) -> bool:
    """Is this data too old to rely on?"""
    return freshness_score(timestamp, volatility) < threshold


def decay_weight(timestamp: datetime, half_life_days: float = 90) -> float:
    """Exponential decay weight: 1.0 at t=0, 0.5 at half_life_days."""
    days = age_days(timestamp)
    return 2.0 ** (-days / half_life_days)


def format_age(timestamp: datetime) -> str:
    """Human-readable age: '2 hours ago', '3 days ago', '6 months ago'."""
    seconds = (utcnow() - timestamp).total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds / 60)} minutes ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)} hours ago"
    elif seconds < 2592000:
        return f"{int(seconds / 86400)} days ago"
    elif seconds < 31536000:
        return f"{int(seconds / 2592000)} months ago"
    else:
        return f"{int(seconds / 31536000)} years ago"


# ── Organizational cadence ──

def week_start(date: Optional[datetime] = None) -> datetime:
    """Start of the week (Monday) for a given date."""
    d = date or utcnow()
    return d - timedelta(days=d.weekday())


# First day of the quarter containing the date.
def quarter_start(date: Optional[datetime] = None) -> datetime:
    d = date or utcnow()
    q_month = ((d.month - 1) // 3) * 3 + 1
    return datetime(d.year, q_month, 1, tzinfo=timezone.utc)


# Human-readable quarter name like "Q3 2026".
def quarter_label(date: Optional[datetime] = None) -> str:
    d = date or utcnow()
    q = (d.month - 1) // 3 + 1
    return f"Q{q} {d.year}"


def next_review_date(cadence: str = "weekly", from_date: Optional[datetime] = None) -> datetime:
    """When is the next review based on cadence?"""
    d = from_date or utcnow()
    if cadence == "daily":
        return d + timedelta(days=1)
    elif cadence == "weekly":
        return week_start(d) + timedelta(days=7)
    elif cadence == "monthly":
        if d.month == 12:
            return datetime(d.year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(d.year, d.month + 1, 1, tzinfo=timezone.utc)
    elif cadence == "quarterly":
        return quarter_start(d) + timedelta(days=90)
    else:
        return d + timedelta(days=7)


# ── demo ──
def _demo():
    now = utcnow()
    recent = now - timedelta(hours=2)
    week_old = now - timedelta(days=7)
    year_old = now - timedelta(days=400)

    results = {
        "freshness_recent_STABLE": round(freshness_score(recent, Volatility.STABLE), 2),
        "freshness_week_old_VOLATILE": round(freshness_score(week_old, Volatility.VOLATILE), 2),
        "is_stale_year_old": is_stale(year_old, Volatility.STABLE),
        "decay_weight_90d": round(decay_weight(now - timedelta(days=90), half_life_days=90), 1),
        "format_age": format_age(recent),
        "week_start": week_start().weekday() == 0,
        "quarter_label": quarter_label(now),
        "next_review_weekly": (next_review_date("weekly") - now).days <= 7,
    }

    assert results["freshness_recent_STABLE"] > 0.95
    assert results["freshness_week_old_VOLATILE"] < 0.3
    assert results["is_stale_year_old"] is True
    assert results["decay_weight_90d"] == 0.5
    assert "hours" in results["format_age"]

    return {"temporal_checks": results, "status": "OK"}


if __name__ == "__main__":
    import json
    print(json.dumps(_demo(), indent=2, default=str))
