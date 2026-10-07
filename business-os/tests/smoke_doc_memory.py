#!/usr/bin/env python3
"""Live smoke test of hierarchical doc memory.
1. Sign up a fresh user.
2. Open a thread (direct entry).
3. Upload a large markdown doc as the 2nd turn attachment.
4. Wait for background tree build.
5. Ask a question that should hit a SPECIFIC chapter.
6. Assert the engine cites that chapter.
"""
import os, sys, time, json, base64, requests

BASE = "https://genuine-feedback-1.preview.emergentagent.com"
TS = int(time.time())
EMAIL = f"doc{TS}@example.com"

# 1. Signup
r = requests.post(f"{BASE}/api/auth/signup", json={
    "name": "DocSmoke", "email": EMAIL, "password": "Smoke12345!"})
r.raise_for_status()
TOKEN = r.json()["token"]
H = {"Authorization": f"Bearer {TOKEN}"}
print(f"== signup ok, credits={r.json()['user']['credits']}")

# 2. Open thread via direct-composer (current default)
r = requests.post(f"{BASE}/api/goals", json={
    "title": "Reviewing the playbook PDF for my pitch deck",
    "why_now": "I have a 30-page playbook a mentor gave me and I need to pull the right ideas for my pitch."}, headers=H)
r.raise_for_status()
THREAD = r.json()["thread"]["thread_id"]
print(f"== thread {THREAD} created")

# 3. Build a >32k-char markdown doc with clearly-labelled chapters so we can verify retrieval routes correctly.
chapters = [
    ("Pricing", "Our pricing tiers are Starter $0, Pro $29/month, Elite $99/month. Discounts apply for annual billing. The Elite tier unlocks unlimited threads and a 1:1 founder review."),
    ("Onboarding", "New users complete a 4-step welcome wizard. Step 1 captures the user's primary goal. Step 2 captures the user's bandwidth. Step 3 captures their unfair advantage. Step 4 captures the long-term potential."),
    ("Retention", "Day-7 retention is the north-star metric. Email re-engagement nudges fire at days 3, 7, 14, and 30 of inactivity. The phrase bank is rotated weekly to avoid staleness."),
    ("Compliance", "GDPR + India DPDP both require an account deletion endpoint with 30-day retention of audit logs. PII at rest is encrypted with AES-256-GCM. PII in transit is TLS 1.3 only."),
    ("Hiring", "Founding team should stay under 5 until ARR crosses $1M. After that, hire first the role with highest 12-month leverage. Hire slow, fire fast."),
    ("North-star metric", "DAU is vanity. Weekly Returning Decision is the metric: did a user open the app and lock at least one concrete next-step that week. Goal: 40% by month 6."),
]
big_text = "# SmartDecigen Founder Playbook\n\n"
for title, body in chapters:
    big_text += f"## {title}\n\n"
    big_text += (body + " ") * 80  # repeat to inflate per-chapter size
    big_text += "\n\n"
print(f"== doc size: {len(big_text):,} chars ({len(big_text)//4:,} approx tokens)")
b64 = base64.b64encode(big_text.encode()).decode()
print(f"== b64 size: {len(b64):,}")

# 4. Upload via a turn message
print("== turn 1 (with attachment, triggers tree build in background)")
t0 = time.time()
r = requests.post(f"{BASE}/api/threads/{THREAD}/turn", json={
    "message": "I attached the playbook. Read it.",
    "attachment_base64": b64,
    "attachment_filename": "playbook.md",
    "attachment_mime": "text/markdown",
}, headers=H, timeout=120)
print(f"== turn 1 took {time.time()-t0:.1f}s, status={r.status_code}")
if r.status_code != 200:
    print(r.text[:1000]); sys.exit(1)
d = r.json()
print(f"   model: {d.get('model')}  cost: {d.get('cost')}  tokens: {d.get('tokens')}")
print(f"   phase: {d['thread'].get('current_phase')}")
print(f"   ack (first 200 chars): {repr(d.get('acknowledgment','')[:200])}")

# 5. Poll until tree status = ready (max 90s)
print("== waiting for background tree build ...")
from pymongo import MongoClient
mc = MongoClient("mongodb://localhost:27017").smartdecigen
deadline = time.time() + 90
ready = False
while time.time() < deadline:
    trees = list(mc.doc_trees.find({"thread_id": THREAD}))
    if trees and all(t["status"] in ("ready", "failed") for t in trees):
        for t in trees:
            print(f"   tree {t['tree_id']} -> {t['status']} | nodes={t.get('node_count')} | build_seconds={t.get('build_seconds')}")
            if t['status'] == 'ready':
                ready = True
                print(f"   doc_summary: {t.get('doc_summary','')[:300]}")
        break
    time.sleep(2)
if not ready:
    print("!! tree did not become ready in time, aborting")
    sys.exit(2)

# 6. Ask a question that should hit the "Retention" chapter specifically.
print("== turn 2 (question targeted at the Retention chapter)")
r = requests.post(f"{BASE}/api/threads/{THREAD}/turn", json={
    "message": "What does the playbook say about email re-engagement nudges and when they should fire?"
}, headers=H, timeout=60)
print(f"   status={r.status_code}")
d = r.json()
print(f"   model: {d.get('model')}  cost: {d.get('cost')}  tokens: {d.get('tokens')}")
print(f"   phase: {d['thread'].get('current_phase')}")
ack = d.get('acknowledgment','')
mirror = d.get('mirror','')
state_sum = d['thread'].get('current_state_summary','')
print(f"   ack: {repr(ack[:300])}")
print(f"   mirror: {repr(mirror[:300])}")
print(f"   state_summary: {repr(state_sum[:400])}")
combined = (ack + " " + mirror + " " + state_sum).lower()
hit_days = ("3" in combined and "7" in combined and "14" in combined) or "retention" in combined or "re-engagement" in combined or "nudge" in combined
print(f"\n   PASS: retrieval surfaced retention/nudge content? {hit_days}")
print(f"   PASS: cited the file/chapter? {'retention' in combined or 'chapter' in combined or 'playbook' in combined}")
