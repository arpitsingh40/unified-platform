"""SALAAR People Layer — Phase 5+6: People Graph + Behavior Scanner.
Every person around the founder is a node. SALAAR profiles their incentives,
patterns, and behavior — applying psychology lenses silently."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from db import db, orgs_col, members_col, tasks_col, threads_col

log = logging.getLogger("salaar.people")

# People and behavior collections backing the graph.
SALAAR_PEOPLE_COL = db["salaar_people"] if db is not None else None
SALAAR_BEHAVIOR_COL = db["salaar_behavior"] if db is not None else None


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


# Generate a random unique ID.
def _uid():
    import uuid
    return str(uuid.uuid4())


# ── Behavior patterns the psychology lenses detect ──
BEHAVIOR_PATTERNS = {
    "gaslighting": {
        "lens": "berdee_psychopaths",
        "triggers": ["crazy", "imagining things", "you're overreacting", "never said that",
                     "making me feel", "twisting my words", "you always", "you're too sensitive",
                     "that didn't happen", "i don't remember that"],
        "severity": "critical",
        "insight": "Gaslighting detected — reality distortion pattern. The person denies observable facts to control perception.",
    },
    "covert_aggression": {
        "lens": "berdee_psychopaths",
        "triggers": ["undermining", "behind my back", "passive aggressive", "sabotaging",
                     "sweet to my face", "talks bad about", "spreading rumors", "undercutting"],
        "severity": "high",
        "insight": "Covert aggression — hostile behavior disguised as innocent. Pattern: charm in public, damage in private.",
    },
    "envy_pattern": {
        "lens": "greene_human_nature",
        "triggers": ["jealous of", "envious", "why do they get", "they don't deserve",
                     "constantly comparing", "bitter about", "resentful", "can't stand their success"],
        "severity": "medium",
        "insight": "Envy pattern — this person's decisions may be driven by comparison, not objective interest.",
    },
    "grandiosity": {
        "lens": "greene_human_nature",
        "triggers": ["i'm the only one who", "nobody else can", "without me this fails",
                     "i built this", "they owe everything to me", "indispensable", "irreplaceable"],
        "severity": "high",
        "insight": "Grandiosity — inflated self-importance. When challenged, this person will defend their position over the outcome.",
    },
    "defensiveness_loop": {
        "lens": "greene_human_nature",
        "triggers": ["won't admit", "never wrong", "always defends", "can't take feedback",
                     "blames others", "it's not my fault", "defensive", "makes excuses"],
        "severity": "medium",
        "insight": "Defensiveness loop — this person cannot process feedback. They externalize all failure.",
    },
    "people_pleasing": {
        "lens": "kishimi_courage",
        "triggers": ["afraid to upset", "can't say no", "everyone expects", "what will they think",
                     "trying to keep everyone happy", "don't want to disappoint", "seeking approval",
                     "need them to like me", "avoiding conflict"],
        "severity": "medium",
        "insight": "People-pleasing — decisions driven by others' approval, not the mission. The founder is subordinating their task to others' tasks.",
    },
    "fear_of_dislike": {
        "lens": "kishimi_courage",
        "triggers": ["scared of being", "don't want them to think", "they'll hate me",
                     "can't risk the relationship", "what if they leave", "afraid to fire",
                     "keeping them around because", "don't have the heart to"],
        "severity": "high",
        "insight": "Fear of being disliked — the founder is tolerating harm to avoid social discomfort. This is the deepest constraint on decision quality.",
    },
    "persuasion_manipulation": {
        "lens": "adams_persuasion",
        "triggers": ["convincing me to", "talked me into", "sweet talked", "smooth talked",
                     "won me over but", "felt manipulated", "pushed into", "pressured to"],
        "severity": "medium",
        "insight": "Persuasion-as-manipulation — someone deployed persuasion tactics where interests were not aligned.",
    },
}


def extract_people_from_text(text: str) -> list[str]:
    """Extract person mentions from text. Simple approach: scan for known role words + proper nouns.
    Returns list of person keys (e.g., 'cofounder', 'investor_x', 'employee_cto')."""
    if not text:
        return []
    people = set()
    roles = {
        "cofounder": ["cofounder", "co-founder", "co founder"],
        "investor": ["investor", "vc", "board member", "angel"],
        "employee": ["employee", "team member", "hire", "report", "engineer", "designer", "salesperson"],
        "customer": ["customer", "client", "account", "user"],
        "competitor": ["competitor", "rival", "other company"],
        "partner": ["partner", "vendor", "supplier", "agency"],
        "advisor": ["advisor", "mentor", "coach", "consultant"],
    }
    lower = text.lower()
    for role, keywords in roles.items():
        for kw in keywords:
            if kw in lower:
                people.add(role)
                break
    return list(people)


def get_or_create_person(org_id: str, person_key: str, role: str = "") -> dict:
    """Get existing person profile or create one."""
    if SALAAR_PEOPLE_COL is None:
        return {"id": _uid(), "org_id": org_id, "person_key": person_key, "role": role}
    existing = SALAAR_PEOPLE_COL.find_one({"org_id": org_id, "person_key": person_key})
    if existing:
        return existing
    doc = {
        "id": _uid(), "org_id": org_id, "person_key": person_key, "role": role,
        "first_seen_at": _now(), "last_seen_at": _now(),
        "mention_count": 0, "positive_mentions": 0, "negative_mentions": 0,
        "red_flags": [], "behavior_patterns": [],
        "promises_made": 0, "promises_kept": 0,
        "decisions_involved": 0, "decisions_blocked": 0,
        "influence_score": 0.0, "trust_score": 50.0,
    }
    SALAAR_PEOPLE_COL.insert_one(doc)
    return doc


def update_person_mention(person_id: str, sentiment: str = "neutral"):
    """Record a mention. sentiment: positive, negative, neutral."""
    if SALAAR_PEOPLE_COL is None:
        return
    inc = {"mention_count": 1}
    if sentiment == "positive":
        inc["positive_mentions"] = 1
    elif sentiment == "negative":
        inc["negative_mentions"] = 1
    SALAAR_PEOPLE_COL.update_one(
        {"id": person_id},
        {"$inc": inc, "$set": {"last_seen_at": _now()}}
    )


def scan_behavior(text: str, person_id: str, org_id: str) -> list[dict]:
    """Apply psychology lenses to detect behavior patterns. Returns list of detected patterns."""
    if not text:
        return []
    hay = text.lower()
    detected = []
    for pattern_key, pattern in BEHAVIOR_PATTERNS.items():
        if not any(t in hay for t in pattern["triggers"]):
            continue
        detected.append({
            "pattern_key": pattern_key,
            "lens": pattern["lens"],
            "severity": pattern["severity"],
            "insight": pattern["insight"],
            "matched_at": _now(),
        })
        # Store behavior event
        if SALAAR_BEHAVIOR_COL is not None:
            SALAAR_BEHAVIOR_COL.insert_one({
                "id": _uid(), "org_id": org_id, "person_id": person_id,
                "pattern_key": pattern_key, "lens": pattern["lens"],
                "severity": pattern["severity"], "matched_text": text[:500],
                "at": _now(),
            })
    # Update person profile with red flags
    if detected and SALAAR_PEOPLE_COL is not None:
        flags = [d["pattern_key"] for d in detected if d["severity"] in ("critical", "high")]
        if flags:
            SALAAR_PEOPLE_COL.update_one(
                {"id": person_id},
                {"$addToSet": {"red_flags": {"$each": flags}},
                 "$push": {"behavior_patterns": {"$each": [d["pattern_key"] for d in detected]}}}
            )
        # Adjust trust score
        severity_map = {"critical": -15, "high": -8, "medium": -3}
        adjustment = sum(severity_map.get(d["severity"], 0) for d in detected)
        if adjustment != 0:
            SALAAR_PEOPLE_COL.update_one(
                {"id": person_id},
                {"$inc": {"trust_score": max(-50, min(50, adjustment))}}
            )
    return detected
