# SmartDecigen Deep Discussion Engine — Plan

> STATUS: Phase 1 POC DONE (12/12 checks). Phase 2 V1 app DONE + tested (100% backend 14/14, 100% frontend, testing agent iteration_1). Auth was built in Phase 2 (email/password JWT, multi-user isolation verified). Remaining (future): Phase 3 KPI dashboards from telemetry, felt-understood micro-prompt, Stripe credit top-ups, account deletion.

## 1) Objectives
- Deliver a **goal-anchored accountability companion** where each interaction closes the gap between **knowing and doing**.
- Implement the **GoalThread** component exactly as specified: **4 living fields as the primary UI**, bounded context, **1 LLM call/turn**, deterministic rolling signals, and **pure-function re-engagement**.
- Ensure the system can reliably detect and reinforce: **next action (24–48h)**, **acknowledgment vs setback**, **silence**, and **what changed**.
- Build an MVP app (FastAPI + React + MongoDB) that feels **premium/minimal** and **not like a chatbot**.

## 2) Implementation Steps

### Phase 1 — Core Flow POC (Isolation; blocked until key)
**Core = deterministic thread state + single-call turn engine + re-engagement delta line.**

**User stories (POC)**
1. As a user, I can simulate a goal thread and see the 4 living fields update each turn with **one LLM call**.
2. As a user, I can return after 7+ days and get a **single deterministic re-engagement line** (or silence).
3. As a user, I can send “I did it” and the system updates **execution_consistency** without another model call.
4. As a user, I can send a setback message and receive an acknowledgment + refreshed easiest path without recap.
5. As a builder, I can confirm prompts stay bounded (no raw history) and token use remains stable over long threads.

**Steps**
1. **Websearch (best practices)**: Anthropic structured JSON output, retry/fallback patterns, and safe prompt compaction patterns.
2. Add backend env requirement: `ANTHROPIC_API_KEY` (user adds to `/app/backend/.env`).
3. Create `/app/backend/poc/test_core.py`:
   - Implements the 6-step pipeline with strict boundaries:
     - Step 1 anchor load (4 living fields)
     - Step 2 substrate refresh (pure)
     - Step 3 intent classify (pure rules)
     - Step 4 single LLM call (Opus 4.8 primary; Haiku fallback)
     - Step 5 state update (overwrite living fields; append message)
     - Step 6 telemetry event emission (stdout/json)
   - Includes the **pure re-engagement function** + founder-locked `PHRASE_BANK`.
   - Runs a simulated multi-week scenario to validate: update/question/setback/silence_breaker.
4. Define the **LLM output schema** (JSON only):
   - `{acknowledgment, refreshed_easiest_path, refreshed_next_action, refreshed_open_question, optional_skip_list, substrate_signals:{emotional_temperature, action_done, contradictions[]}}`
5. Add Opus→Haiku fallback + minimal retries (network/429/5xx).
6. Validate:
   - JSON parse stability
   - prompt boundedness
   - re-engagement line correctness + null behavior
7. Do not proceed until POC passes consistently.

### Phase 2 — V1 App Development (MVP around proven core; auth deferred until Phase 4)
**Build the product shell that makes it feel like a “situation pane” not chat.**

**User stories (V1)**
1. As a user, I can create a goal and immediately see a thread with the **4 living fields**.
2. As a user, I always see **one open question** above the composer so I know what tension is unresolved.
3. As a user, after I send a message I get a **brief companion acknowledgment** + refreshed easiest path/next action.
4. As a user, I can expand **Show history** to view the raw message log without it being the primary UI.
5. As a user, I can see my goals dashboard with **active/paused/graduated/released** status and pace indicator.

**Backend (FastAPI)**
- MongoDB collections:
  - `goal_threads` (living fields + messages[] + status)
  - `substrate_events` (append-only events powering rolling fields)
  - `telemetry_events`
- Endpoints (unauthenticated for V1 testing):
  - `POST /api/goals` (create goal + create GoalThread)
  - `GET /api/goals` (list dashboard)
  - `GET /api/threads/{thread_id}` (fetch thread pane data)
  - `POST /api/threads/{thread_id}/turn` (runs 6-step pipeline)
  - `POST /api/threads/{thread_id}/reengage` (returns re-engagement line; pure)
- Implement rolling fields computation deterministically from substrate events (14d windows).
- Implement silence rule: if ≥14 days quiet during active push, next turn forces `silence_breaker` intent.
- Summary regeneration every 10 messages using **Haiku** (one extra call only when threshold reached).

**Frontend (React)**
- Pages:
  - Goals Dashboard (minimal list + status + pace)
  - Goal Thread view (“Situation Pane”):
    - Re-engagement line (if present)
    - Current state summary (3 lines)
    - Open question (1 line, pinned above composer)
    - Easiest path (1–2 lines)
    - Next action (1 line; 24–48h framing)
    - Composer
    - “Show history” expander
- Styling: ultra-minimal, whitespace-heavy, premium typography, subtle motion; avoid chat bubble UI.

**Phase 2 close-out**
- Run 1 round of end-to-end testing (create goal → turns → field refresh → history expander → dashboard updates).

### Phase 3 — Instrumentation + Accountability Tightening
**Make it measurably about behavior change.**

**User stories (Phase 3)**
1. As a user, I can mark “done” explicitly and see execution consistency reflect it.
2. As a user, when I return after absence, I see what changed (or silence) without recap.
3. As a user, I can pause/release a goal and the system stops applying silence pressure.
4. As a user, I can see lightweight progress signals (pace calibration) without gamification.
5. As a builder, I can view KPI dashboards from telemetry events.

**Steps**
- Telemetry events + KPI computations:
  - 7-day return rate, re-engagement line open rate, turns/week, felt-understood micro-prompt response rate, goal completion within 90d.
- Add “felt-understood” micro-prompt trigger (non-blocking) after dwell-time; store response.
- Improve action_done detection rules (hybrid: user explicit + LLM signal piggyback).
- Add goal graduation/release flows and ensure re-engagement/silence rules respect status.
- End-to-end testing round.

### Phase 4 — Authentication (Email/Password JWT) + Multi-user Data Isolation

**User stories (Auth)**
1. As a user, I can sign up/login and only see my own goals/threads.
2. As a user, my threads persist across devices.
3. As a user, logging out clears access.
4. As a builder, I can verify thread isolation with two accounts.
5. As a user, I can delete my account and data.

**Steps**
- Add auth endpoints + JWT middleware.
- Add user_id to all documents and enforce access control.
- Run end-to-end tests including multi-user scenarios.

## 3) Next Actions (Immediate)
1. **User**: Add `ANTHROPIC_API_KEY=sk-ant-...` to `/app/backend/.env` and reply “added”.
2. Build Phase 1 POC script (`test_core.py`) implementing the full pipeline + pure re-engagement.
3. Run POC simulations; fix until stable JSON + correct deterministic re-engagement.
4. Once green, proceed to Phase 2 V1 app build.

## 4) Success Criteria
- **POC**: Single-turn engine returns valid JSON every time; Opus primary + Haiku fallback verified; prompts remain bounded; re-engagement line is deterministic and silence-preserving.
- **V1 UX**: Primary UI shows only the 4 living fields + composer; raw history hidden; one open question always visible.
- **Accountability**: Next action always 24–48h; acknowledgment vs setback intents handled; silence rule triggers appropriately.
- **Metrics wired**: Telemetry events emitted; KPI computations runnable from stored events.
- **Reliability**: No more than 1 LLM call per turn (except summary every 10 messages); system works end-to-end without breaking flows.
