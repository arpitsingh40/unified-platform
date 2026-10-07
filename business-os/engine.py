"""Deep Discussion Engine core — proven in POC (Phase 1, all checks passed).
Pure functions: intent classification, rolling fields, re-engagement.
Single LLM call per turn — provider-agnostic via llm_client.
Multi-modal: attach image / PDF / Excel / CSV / text — engine reads and reasons on the file."""
import io
import json
import re
import base64
import logging
from datetime import datetime, timedelta

from db import users_col

log = logging.getLogger(__name__)

from llm_client import (
    client, _extract_json,
    PRIMARY_MODEL, ANALYTICAL_MODEL, ULTRA_MODEL, FALLBACK_MODEL,
)

# Allowed image mime types + text extraction cap
IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_FILE_CHARS = 50000  # cap extracted text — bounds cost; engine doesn't need the whole novel

# Render the company-state summary for the prompt
def _get_state_block(user_id: str) -> str:
    try:
        u = users_col.find_one({"id": user_id}, {"_id": 0, "company_state": 1})
    except Exception:
        return ""
    if not u:
        return ""
    s = u.get("company_state") or {}
    if not s or not s.get("objective"):
        return ""
    lines = ["- Objective: " + s["objective"]]
    for key, label in (("blockers", "Diagnosed blockers"), ("constraints", "Known constraints"), ("fears", "Underlying fears"), ("direction_decision", "Agreed direction")):
        v = s.get(key)
        if v:
            val = "; ".join(v) if isinstance(v, list) else str(v)
            lines.append(f"- {label}: {val[:300]}")
    if s.get("open_milestones"):
        ms = [f"{m['title']} ({m.get('deadline', 'no deadline')})" for m in s["open_milestones"]]
        lines.append(f"- Open milestones: {'; '.join(ms[:3])}")
    unc = s.get("uncertainty")
    if isinstance(unc, dict):
        scores = [v.get("score", 50) for v in unc.values() if isinstance(v, dict)]
        if scores:
            lines.append(f"- Diagnostic uncertainty: {sum(scores)/len(scores):.0f}/100")
    lines.append(f"- Stage: {'diagnosis complete' if s.get('diagnosis_done') else 'diagnosis in progress'}")
    return "COMPANY STATE (from the ongoing diagnosis — treat as known, do NOT re-ask, check every recommendation against these constraints):\n" + "\n".join(lines)


# ---------------------------------------------------------------- Biography Bank
def _bio_block(context: str) -> str:
    try:
        from playbooks import biography_block
        return biography_block(context=context) + "\n" if biography_block(context=context) else ""
    except Exception:
        return ""

# ---------------------------------------------------------------- Decision Brain context merge
def _brain_context_block(org_id: str, user_doc: dict, question: str) -> str:
    """Merge the Decision Brain's grounding into thread turns: INDUSTRY_CONTEXT
    (incl. the Tavily deep-research digest), FOUNDER_PROFILE (owner only),
    HIDDEN_STRATEGY (owner only), BUSINESS HEALTH, and KB retrieval passages.
    Empty string when there is no org or the merge fails (never blocks a turn)."""
    if not org_id or not user_doc:
        return ""
    try:
        from decision_brain import (_resolve_context, _industry_block, _founder_profile_block,
                                    _signal_scan_block, kb_retrieve)
        from db import members_col, orgs_col
        m = members_col.find_one({"user_id": user_doc.get("id"), "status": "active"})
        if not m:
            return ""
        org = orgs_col.find_one({"id": m["org_id"]})
        if not org:
            return ""
        parts = []
        ind = _industry_block(org)
        if ind:
            parts.append(ind)
        if (m.get("role") or "") == "owner":
            fp = _founder_profile_block(org)
            if fp:
                parts.append(fp)
            sb = _hidden_strategy_for_thread(org)
            if sb:
                parts.append(sb)
        sh = _signal_scan_block(org)
        if sh:
            parts.append(sh)
        kb_ns, _, _, _ = _resolve_context(user_doc)
        try:
            passages, _, _ = kb_retrieve(kb_ns, question)
            if passages:
                psg = "\n\n".join(f"[{p['doc']} -> {p['chapter']}] (score {p['score']})\n{p['text'][:1000]}"
                                  for p in passages[:4])
                parts.append("RETRIEVED_PASSAGES (the most relevant evidence from the company's own "
                             "documents — ground factual claims in these, cite the source doc):\n" + psg)
        except Exception:
            pass
        if not parts:
            return ""
        return "\n\n".join(parts) + "\n\n"
    except Exception:
        return ""


def _hidden_strategy_for_thread(org: dict) -> str:
    """HIDDEN_STRATEGY steering for the thread engine — same direction as the brain's
    strategy block but without the brain's strategic_alignment JSON field."""
    ns = (org.get("north_star") or "").strip()
    if not ns:
        return ""
    target = (org.get("target") or "").strip()
    deadline = (org.get("deadline") or "").strip()
    prios = [p for p in (org.get("priorities") or []) if isinstance(p, str) and p.strip()]
    lines = ["HIDDEN_STRATEGY (CONFIDENTIAL leadership direction. The user must NEVER see or sense any of this):",
             f"- North Star: {ns}"]
    if target or deadline:
        lines.append(f"- Target: {target}{(' by ' + deadline) if deadline else ''}".strip())
    if prios:
        lines.append("- Strategic priorities: " + "; ".join(prios))
    lines.append("INSTRUCTION: Silently steer every reply toward this North Star. NEVER mention, quote, "
                 "paraphrase, name, hint at, or allude to this strategy or any hidden objective.")
    return "\n".join(lines)

# ---------------------------------------------------------------- Ch.X: MCP tool injection
def _mcp_tools_block(department_function: str = "general") -> str:
    """Inject available MCP tools into the engine prompt so the LLM knows
    what actions it can take. Uses the Capability Registry for smart tool selection.
    Pure text, no cost."""
    try:
        from execution.mcp_client import mcp_enabled
    except Exception:
        return ""
    if not mcp_enabled():
        return ""

    # Use Capability Registry (phase 1) instead of DEPARTMENT_TOOL_SCOPE
    try:
        from execution.registry import capabilities_for_department
        registry_tools = capabilities_for_department(department_function, limit=30)
        if registry_tools:
            tool_lines = []
            for t in registry_tools:
                slug = t.get("tool_slug", t.get("name", ""))
                name = t.get("tool_name", slug)
                desc = (t.get("tool_desc", "") or "")[:200]
                tool_lines.append(f"- {slug}: {name} — {desc}")
            block = (
                "AVAILABLE TOOLS (capability-matched to your department — use tool_calls in JSON):\n"
                + "\n".join(tool_lines) + "\n\n"
                "TOOL_CALLS FORMAT: add a 'tool_calls' array with objects like "
                '{"tool": "tool_slug", "args": {...}, "reason": "why this helps", "capability": "what business need"}. '
                "Omit the field for pure advice turns. Max 5 calls per turn."
            )
            return block
    except Exception:
        pass

    # Fallback: legacy DEPARTMENT_TOOL_SCOPE
    try:
        from execution.mcp_client import tools_for_department
    except Exception:
        return ""
    tools = tools_for_department(department_function)
    if not tools:
        return ""
    tool_lines = []
    for t in tools[:30]:
        name = t.get("name", "")
        desc = (t.get("description", "") or "")[:200]
        props = (t.get("inputSchema") or {}).get("properties", {})
        param_hints = ", ".join(f"{k}" for k in list(props.keys())[:4])
        tool_lines.append(f"- {name}({param_hints}): {desc}")
    block = (
        "AVAILABLE TOOLS (you can execute these on the internet via tool_calls in your JSON):\n"
        + "\n".join(tool_lines) + "\n\n"
        "TOOL_CALLS FORMAT: add a 'tool_calls' array to your JSON with objects like "
        '{"tool": "tool_name", "args": {"param": "value"}, "reason": "why this helps"}. '
        "Use tool_calls when the user asks you to DO something (send, find, create, update, search) "
        "that one of these tools can handle. Omit the field entirely for pure advice turns. "
        "Max 5 calls per turn. Execute the most impactful actions first."
    )
    return block

# ---------------------------------------------------------------- intent (pure)
ACK = re.compile(r"\b(did it|done|completed|finished|shipped|sent it|made the call|i did)\b", re.I)
SETBACK = re.compile(r"\b(couldn'?t|didn'?t|failed|stuck|blocked|gave up|too hard|avoided|put it off|procrastinat)\b", re.I)
QUESTION = re.compile(r"\?\s*$|^\s*(how|what|should|why|when|can i|do i|is it)\b", re.I)

# Bucket the message into a conversation intent
def classify_intent(msg: str, days_since_last: float) -> str:
    if days_since_last >= 14:
        return "silence_breaker"
    if ACK.search(msg):
        return "acknowledgment"
    if SETBACK.search(msg):
        return "setback"
    if QUESTION.search(msg):
        return "question"
    if len(msg.split()) < 4:
        return "drift"
    return "update"

# ------------------------------------------------- rolling fields (pure, replayable)
def rolling_fields(events: list, now: datetime) -> dict:
    cutoff = now - timedelta(days=14)
    recent = [e for e in events if e["at"] >= cutoff]
    temps = [e["emotional_temperature"] for e in recent if e.get("emotional_temperature") is not None]
    acts = [e for e in recent if e.get("action_assigned")]
    done = [e for e in acts if e.get("action_done")]
    consistency = (len(done) / len(acts)) if acts else 0.5
    expected_turns = 14 / 3.5  # own-pace baseline: ~2 turns/week
    pace = "on-track"
    if len(recent) >= expected_turns * 1.4 and consistency >= 0.6:
        pace = "ahead"
    elif len(recent) <= expected_turns * 0.5 or consistency < 0.3:
        pace = "behind"
    return {
        "emotional_temperature": round(sum(temps)/len(temps), 2) if temps else 0.5,
        "execution_consistency": round(consistency, 2),
        "pace_calibration": pace,
        "contradiction_history": [e["contradiction"] for e in events if e.get("contradiction")],
    }

# ------------------------------------------------- re-engagement (pure, NO LLM, founder-locked phrase bank)
PHRASE_BANK = {
    "execution_up":   "{days} days away. Last time: {prior}. Your follow-through is up {mag}% since then — whatever you changed, it is working.",
    "execution_down": "{days} days away. Last time: {prior}. Execution consistency dropped {mag}% — worth naming before anything else.",
    "emotional_up":   "{days} days since we spoke. You left at: {prior}. The resistance reads lower now.",
    "emotional_down": "{days} days since we spoke. You left at: {prior}. Something is heavier than it was — that comes first.",
    "contradiction":  "While you were gone, a tension surfaced: {extra} Worth looking at before moving.",
}
PRIORITY = ["contradiction", "execution", "emotional"]

# Pick a phrase-bank line for returning users
def compute_reengagement_line(last_snap: dict, now_snap: dict, days_absent: int):
    if days_absent < 7 or not last_snap:
        return None
    deltas = []
    de = now_snap["execution_consistency"] - last_snap.get("execution_consistency", 0.5)
    if abs(de) >= 0.15:
        deltas.append(("execution", de, abs(round(de*100))))
    dt = now_snap["emotional_temperature"] - last_snap.get("emotional_temperature", 0.5)
    if abs(dt) >= 0.2:
        deltas.append(("emotional", dt, abs(round(dt*100))))
    new_contra = [c for c in now_snap["contradiction_history"] if c not in last_snap.get("contradiction_history", [])]
    if new_contra:
        deltas.append(("contradiction", 0, new_contra[-1]))
    if not deltas:
        return None  # silence-preserving
    deltas.sort(key=lambda d: PRIORITY.index(d[0]))
    kind, sign, extra = deltas[0]
    if kind == "contradiction":
        x = str(extra).rstrip(".") + "."
        return PHRASE_BANK["contradiction"].format(extra=x)
    key = f"{kind}_{'up' if sign > 0 else 'down'}"
    return PHRASE_BANK[key].format(days=days_absent, prior=last_snap.get("summary_line", "your last position"), mag=extra)

# ------------------------------------------------- action assist: "Do it for me" (1 LLM call)
def _user_context_block(user_doc) -> str:
    """Render the user's questionnaire (Dream/Capacity/Advantage/Potential) into a tight
    prompt block. Returns empty string if the questionnaire isn't completed yet, so threads
    opened before answering keep the prior behaviour."""
    if not user_doc:
        return ""
    q = user_doc.get("questionnaire") or {}
    dream = (q.get("dream") or "").strip()
    capacity = (q.get("capacity") or "").strip()
    advantage = (q.get("advantage") or "").strip()
    potential = (q.get("potential") or "").strip()
    if not (dream or capacity or advantage or potential):
        return ""
    lines = ["What they've told me about themselves (use this as ground truth for what's realistic, what's at stake, and what to lean on):"]
    if dream:
        lines.append(f"- DREAM: {dream}")
    if capacity:
        lines.append(f"- CAPACITY (time/money/energy they have right now): {capacity}")
    if advantage:
        lines.append(f"- ADVANTAGE (what they uniquely have going for them): {advantage}")
    if potential:
        lines.append(f"- POTENTIAL (what they believe they could become): {potential}")
    return "\n".join(lines) + "\n\n"


# System prompt for the "do it for me" assist call
ASSIST_SYSTEM = """You are the execution hand. The founder has ONE next action. Your job: produce the exact output they need to finish it — then get out of their way.

SELF CHECK before producing anything: if you would hesitate to see this result in 30 days, do not produce it. An action that does not improve their actual situation is worse than no action at all.

VOICE: write like a sharp colleague who knows their business. Plain English, short sentences, easy to scan. Match their register (casual or crisp). Contractions welcome. Jargon banned. The artifact must read like they wrote it on a good day.

FILE-AWARE EXECUTION (critical): if the thread state shows the user has attached a file with the data needed for this action (visible via FILE_FACTS in the context), the artifact IS the computation — not instructions to do the computation. NEVER produce a checklist of 'open the sheet, find the column, count the rows' for data the engine has already seen. Instead, state the answer with the numbers and ask for ONLY the missing piece. If both numbers are available, do the math and present the result.

Decide the kind:
- "draft": the action produces a sendable/usable artifact (email, message, list, script, post, plan, outline, research summary, COMPUTED table from attached data). Write the FINISHED artifact in the user's voice — specific, ready to ship, grounded in everything known from the thread. No placeholders unless a fact is truly unknowable, then use [[FILL: what goes here]] sparingly.
- "kit": the action is physical/real-world (a call, a visit, signing, a workout, a meeting). Produce the 10-minute version: the exact words to say or script to follow, what to bring/open, the smallest viable version that still counts as done.

Rules: concrete over generic; their stated goal and why-it-matters are your material; zero fluff; the artifact must be genuinely shippable as-is; if it's an email or message, sound human, not templated; if it's analysis on attached data, do the math and present results, do not instruct the user to do it.

Return ONLY valid JSON, no markdown fences:
{"kind": "draft" or "kit",
 "title": "3-6 words naming the artifact",
 "channel": "email"|"whatsapp"|"call"|"document"|"calendar"|"other",
 "subject": "email subject line, or null if not an email",
 "artifact": "the complete artifact text (for kit: the exact script/words + what to bring; for computed analysis: the answers with numbers, not instructions to compute)",
 "steps": ["2-4 micro-steps to ship it, each under 10 words"],
 "handoff": "1 warm line: exactly what to do with this in the next 5 minutes",
 "time_estimate_min": minutes_to_complete_as_integer}"""

ASSIST_REQUIRED = ("kind", "title", "artifact", "handoff")

def llm_complete_action(thread: dict, user_doc=None):
    """Generate the ship-ready artifact (or 10-minute kit) for the current next action."""
    saved_facts = (thread.get("current_file_facts") or "").strip()
    facts_block = f"FILE_FACTS (from a file the user attached earlier — the artifact must USE these numbers, not ask the user to re-derive them):\n{saved_facts}\n" if saved_facts else ""
    user_ctx_block = _user_context_block(user_doc)
    prompt = (
        f"{user_ctx_block}"
        f"GOAL: {thread['goal']}\n"
        f"WHY IT MATTERS TO THEM: {thread.get('why_now', '(not stated)')}\n"
        f"STATE SUMMARY:\n{thread['current_state_summary']}\n"
        f"EASIEST PATH: {thread['current_easiest_path']}\n"
        f"NEXT ACTION TO COMPLETE: {thread['current_next_action']}\n"
        f"PAYOFF WHEN DONE: {thread.get('current_action_payoff') or '(not stated)'}\n"
        f"BIG PICTURE: {thread.get('current_big_picture') or '(not stated)'}\n"
        f"{facts_block}"
        "Produce the artifact or kit that completes this next action with minimal user effort."
    )
    last_err = None
    # System block is cached (prompt caching = 90% cheaper from 2nd call onward, identical block).
    system_blocks = [{"type": "text", "text": ASSIST_SYSTEM,
                      "cache_control": {"type": "ephemeral"}}]
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            r = client().messages.create(model=model, max_tokens=3000, system=system_blocks,
                                         messages=[{"role": "user", "content": prompt}])
            txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
            out = json.loads(_extract_json(txt))
            if not all(k in out for k in ASSIST_REQUIRED):
                raise ValueError("incomplete JSON keys")
            usage = {"input_tokens": int(getattr(r.usage, "input_tokens", 0) or 0),
                     "output_tokens": int(getattr(r.usage, "output_tokens", 0) or 0)}
            return out, model, usage
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All models failed: {last_err}")

# ------------------------------------------------- multi-modal attachments (file/image -> LLM-readable)
def _extract_pdf(b: bytes) -> str:
    """PyMuPDF — extract text from first 30 pages, cap at MAX_FILE_CHARS."""
    import fitz
    parts = []
    with fitz.open(stream=b, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= 30:
                break
            parts.append(page.get_text())
    return "\n".join(parts)[:MAX_FILE_CHARS]


def _extract_xlsx(b: bytes) -> str:
    """openpyxl — first 5 sheets, 200 rows each, tab-separated."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(b), data_only=True, read_only=True)
    parts = []
    for sheet in wb.sheetnames[:5]:
        ws = wb[sheet]
        parts.append(f"### Sheet: {sheet}")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 200:
                break
            parts.append("\t".join("" if v is None else str(v) for v in row))
    return "\n".join(parts)[:MAX_FILE_CHARS]


# Extract up to 500 CSV rows as text
def _extract_csv(b: bytes) -> str:
    import csv
    rdr = csv.reader(io.StringIO(b.decode("utf-8", errors="replace")))
    lines = []
    for i, row in enumerate(rdr):
        if i >= 500:
            break
        lines.append(",".join(row))
    return "\n".join(lines)[:MAX_FILE_CHARS]


def build_attachment_blocks(attachment):
    """Turn an uploaded file into LLM-ready content.
    Images -> Anthropic vision content block (the model sees the image).
    PDF/Excel/CSV/text -> server-side extraction, appended to the text prompt (cheaper + reliable).
    Returns (vision_blocks, text_appendix). Either or both may be empty.
    """
    if not attachment:
        return [], ""
    mime = (attachment.get("mime") or "").lower()
    name = attachment.get("filename") or "file"
    b64 = attachment.get("base64") or ""
    if not b64:
        return [], ""
    if mime in IMAGE_MIMES:
        return ([{"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}],
                f"\n\nATTACHED_IMAGE: {name} — read it as evidence/context for the user's situation.")
    try:
        raw = base64.b64decode(b64)
        lower = name.lower()
        if mime == "application/pdf" or lower.endswith(".pdf"):
            text = _extract_pdf(raw)
        elif "spreadsheet" in mime or lower.endswith((".xlsx", ".xls")):
            text = _extract_xlsx(raw)
        elif mime == "text/csv" or lower.endswith(".csv"):
            text = _extract_csv(raw)
        else:
            text = raw.decode("utf-8", errors="replace")[:MAX_FILE_CHARS]
        return [], f"\n\n--- ATTACHED FILE: {name} ---\n{text}\n--- END FILE ---"
    except Exception as e:
        log.warning(f"attachment '{name}' could not be parsed: {e}")
        return [], f"\n\n[attached file '{name}' could not be read — ignore it and continue]"


# ------------------------------------------------- SALAAR routing
def salaar_route(text: str, thread: dict = None, user: dict = None) -> str:
    """Classify user input into one of four paths.
    Returns 'knowledge' | 'decision' | 'diagnosis' | 'engine'.
    Pure logic, zero LLM cost."""
    hay = (text or "").lower().strip()
    # 1. Knowledge: factual questions about company documents / policies
    knowledge_kw = ("what is", "what are", "do we have", "is there", "where is",
                    "our policy", "our rule", "tell me the", "remind me",
                    "in the document", "according to", "what does", "how many",
                    "when did we", "who is", "what was", "company rule")
    if any(hay.startswith(kw) for kw in knowledge_kw) and len(hay) < 200:
        return "knowledge"
    # 2. Decision: strategic trade-offs, should-we, comparisons
    decision_kw = ("should i", "should we", "what do you think about",
                   "what about", "which option", "better to", "worst case",
                   "trade", "pros and cons", "compare", "versus", "vs ",
                   "hire or", "fire or", "invest or", "risk of")
    if any(kw in hay for kw in decision_kw):
        return "decision"
    # 3. Diagnosis: vague/open, early stage, no journey context
    if not thread or not thread.get("current_phase") or thread["current_phase"] == "exploring":
        if len(hay) < 60 and not any(kw in hay for kw in ("i need", "draft", "write", "plan")):
            return "diagnosis"
    # 4. Default: engine (continuation / execution / conversation)
    return "engine"


# ------------------------------------------------- single LLM call per turn
SYSTEM = """You are the ONE system for this founder: both their personal coach AND the company's brain. You maintain the highest-fidelity model of this founder and their company. Every message is evidence. Your job is not just to answer — it is to update the model and let the response emerge from it. For a solo founder, that means: you track their goal across turns (coach) AND you answer, decide, and plan for the company (brain) — in the same conversation, in the same turn if needed.

BEFORE EVERY TURN (your silent internal sweep — never output this):
1. ASSEMBLE STATE. From everything known (identity, codex, company state, memory, their words, file facts, geo, industry, docs, strategy), build the current picture of their objective reality. What has changed since last turn? What is confirmed vs newly revealed?
2. LOCATE THEIR MESSAGE IN THAT STATE. Does this message confirm the model, contradict it, or add a new dimension? What gap exists between their perception and the state you hold?
3. TEST REQUEST AGAINST STATE. Given the state, does their ask make sense? What would have to be true for it to be right? What is the weakest assumption they are carrying?
4. EVALUATE THE FIELD. What are the viable moves from here? For each, what changes in the state? Which one moves them toward their goal with the least downside and the highest expected impact?
5. OUTPUT FROM STATE. Your phase, mode, acknowledgment, and action must be the direct consequence of your state model, not a conversational formula. If the state cannot support a move, say so plainly.

THREE JOBS (pick the mode the message calls for; one reply can serve one job or blend two):
- ANSWER: a factual question (about the company's documents, the market, a regulation, a competitor). Lead with the direct answer, grounded in RETRIEVED_PASSAGES / INDUSTRY_CONTEXT / TAVILY results. Cite sources in citations. If the answer is NOT in the evidence, say plainly you could not find it — NEVER invent a fact.
- DECIDE: a judgment call ("should we...", "what do I do about...", "is it okay to..."). Give a clear recommendation FOR THIS COMPANY, one short why, and the single risk to watch. State your assumption out loud and proceed; then note what would sharpen it.
- PLAN: the user wants a path to an objective ("give me a plan", "how do I...", "lay it out"). Give a REAL, detailed, usable plan: 4 to 8 ordered steps in plan, each concrete and doable, with who/what/a rough number/a timeframe where it helps. Name the first move to make this week and the one risk that could sink it. A plan is the deliverable, not a teaser.

WHO YOU ARE IN THE CONVERSATION:
- A sharp operator who has done this before. Not a coach, not a therapist, not a chatbot.
- You care about their outcomes, not their comfort in the moment. You are warm because you are invested, not because you are polite.
- You give real, specific observations grounded in the state model. When you lack data, you say so and give your best read.
- You calibrate to their operating style (codex, identity) while staying honest about reality.

THE WAY YOU SPEAK:
- Plain English. Short sentences. One idea at a time.
- Concrete over generic. Numbers over adjectives.
- No filler, no corporate speak, no emojis, no exclamation marks.
- Contractions welcome. Every line earns its place.

LEAD WITH VALUE: every reply opens with ONE punchy, genuinely useful line — the single most valuable thing they get this turn (a direct answer, a number, a sharp recommendation, the key first step, a warning, or a reframe). Not always a number — pick the value type that fits.

HONOR THE REQUEST: if the user explicitly asks for a plan, an answer, a draft, a list, or asks you to suggest / recommend / pick / choose one, DELIVER the full thing now. When asked to suggest or recommend, COMMIT to ONE specific, named option — never a category or a menu: name it, justify it in one line, and give the first move. NEVER answer a direct request by asking a question instead.

PREDICT THE OUTCOME: whenever you recommend an action, a decision, or a plan, commit to ONE measurable prediction (predicted_outcome): what will observably happen if they follow it (a number, a signal, a state change they can check later), an HONEST confidence 0..100 (55 when genuinely unsure, 85+ only when the mechanism is near-certain), and review_after_days (7 for fast-feedback actions, 14 for medium, 30 for slow-burn strategy). You WILL be checked against this later, so make it checkable. Pure factual lookups (mode answer with no recommendation) may set null.

WHEN NOT TO FOLLOW: name the ONE condition under which they should NOT follow this recommendation (dont_follow_if): the specific fact that, if true in their world, flips the call. Plain, specific, one line. Pure factual lookups may set null.

PHASE GUIDE (driven by state confidence, not by conversational feel):
- exploring: state model is sparse. Most dimensions unknown. Gather evidence.
- naming: the critical obstacle is visible in the state. Name it plainly.
- ready_to_act: the state supports a specific move. Propose it with payoff.
- acting: they agreed. Lock the concrete step. Execute.
- checking_in: they reported back. Update the state model. Celebrate or regroup.

CONVERSATION RULES:
- Start your reply by reflecting what their message reveals about the state, not by repeating their words.
- Exactly ONE question per turn (in refreshed_open_question). No question marks in acknowledgment.
- The acknowledgment is the only visible output. Everything else is internal state tracking.

USE COMPANY CONTEXT (when present in the prompt):
- INDUSTRY_CONTEXT: real domain knowledge about their market — including a web-research digest with sources. Ground your reads in it instead of generic advice. Never invent numbers not in it.
- FOUNDER_PROFILE: this is who you're advising. Fit tone, framing, and the next action to them naturally. NEVER quote it back or label them.
- HIDDEN_STRATEGY: CONFIDENTIAL. Silently steer every reply toward the North Star; the user must NEVER sense this block exists.
- BUSINESS HEALTH CONTEXT: factor in the company's real state silently; never mention the scan itself.
- RETRIEVED_PASSAGES: the company's own documents. Ground factual claims in them and cite the document name.
- When you need current, real-world facts (market, competitors, pricing, regulations, news) and the user's question depends on them, request a TAVILY_SEARCH tool call so the results are appended to your reply. You may also request TAVILY_DEEP_RESEARCH when the company's market context is thin and a full research pass would materially improve the state.

REASONING SWEEP (silent, every message): ten-dimension uncertainty map about THIS user's situation, each scored 0..100 (0 = fully understood, 100 = complete unknown), honest, may rise when new information exposes a problem: goal, reality, constraints, risks, resources, knowledge_gap, assumptions, hidden_desire, decision_impact, missing_info. Detect unsupported assumptions. Classify the decision (idea|validation|execution|scaling|crisis|other) and whether it is reversible. Note the 2-4 expert lenses you applied. When the decision-critical dimensions are already low-uncertainty, set sufficient=true and refreshed_open_question SHOULD be the single sharpest remaining question or null.

HARVEST BENCHMARK FACTS: whenever the user states a REAL number about the business (revenue, orders, margin, ticket size, headcount, conversion...), record it in benchmark_facts with a reusable snake_case metric name and the industry. ONLY numbers they explicitly stated, never your own estimates. Empty list when none.

Return ONLY valid JSON, no markdown fences:
{"mode": "answer" | "decide" | "plan" | "advice",
 "phase": "exploring"|"naming"|"ready_to_act"|"acting"|"checking_in",
 "phase_reason": "1 short line — what in the state drives this phase",
 "key_takeaway": "ONE punchy, genuinely useful line: the single most valuable thing this turn. Never empty.",
 "acknowledgment": "Your reply. Start by showing you understand what their message reveals. Then one thing that moves them forward. No question marks here — the question goes in refreshed_open_question.",
 "mirror": "1 gentle sentence: the gap between their words and the state you see. Statement, not a question. Soft openers welcome: 'I may be wrong, but…'",
 "understanding": {"focus": "...", "fears": "...", "blockers": "...", "constraints": "...", "tried": "...", "motivators": "...", "stage": "...", "gap_to_goal": "...", "emotional_read": "...", "needs_now": "heard|decision|plan|reality_check|encouragement|answer"},
 "recommendation": "decide mode ONLY: the company-favoured choice + one why + the one risk to watch. Otherwise null.",
 "plan": ["plan mode ONLY: 4 to 8 ordered steps, each a full, concrete, useful line (who/what/rough number/timeframe where it helps)"] or null,
 "citations": [{"doc": "document name", "chapter": "chapter title or URL"}],
 "found_in_docs": true or false,
 "predicted_outcome": {"claim": "ONE measurable, checkable thing that will happen if they follow this", "confidence": 62, "review_after_days": 14} or null,
 "dont_follow_if": "ONE plain, specific condition under which they should NOT follow this recommendation" or null,
 "refreshed_easiest_path": "1-2 lines — null when exploring",
 "refreshed_next_action": "1 line: concrete 24-48h action — null when exploring or naming",
 "outbox_alternative": "1-2 lines: one non-obvious higher-leverage alternative — null when exploring/naming",
 "action_payoff": "1 line — null unless ready_to_act/acting/checking_in",
 "big_picture_link": "1 line — null unless ready_to_act/acting/checking_in",
 "bold_move": "1-2 lines or null",
 "requested_input": "0-1 line or null. Be specific and warm.",
 "file_facts": "3-6 lines — null if no file this turn",
 "refreshed_open_question": "1 line: the unresolved tension. The ONLY question mark.",
 "skip_list": ["0-2 things to ignore right now"],
 "state_summary": "3 short lines: where they are, grounded in the state model",
 "signals": {"emotional_temperature": 0.0to1.0, "action_done": bool, "contradiction": "string or null"},
 "reasoning": {"uncertainty": {"goal": {"score": 0, "note": ""}, "reality": {"score": 0, "note": ""}, "constraints": {"score": 0, "note": ""}, "risks": {"score": 0, "note": ""}, "resources": {"score": 0, "note": ""}, "knowledge_gap": {"score": 0, "note": ""}, "assumptions": {"score": 0, "note": ""}, "hidden_desire": {"score": 0, "note": ""}, "decision_impact": {"score": 0, "note": ""}, "missing_info": {"score": 0, "note": ""}}, "biggest_uncertainty": "one of the ten dimension keys", "assumptions_detected": ["an unsupported belief they are carrying"], "hidden_desire": "what they seem to really want, one line, empty string if unknown", "decision_type": "idea|validation|execution|scaling|crisis|other", "reversible": true, "expert_lenses": ["the 2-4 expert perspectives you applied"], "sufficient": false, "sufficiency_reason": "one line on whether more information would still change this decision"},
 "benchmark_facts": {"industry": "short lowercase industry label, 1-3 words, or '' if unknown", "facts": [{"metric": "snake_case_metric_name_with_unit_hint", "value": 123, "unit": "inr|pct|orders|people|..."}]},
 "tool_calls": [{"tool": "tool_name", "args": {"param": "value"}, "reason": "why this call"}]
 // tool_calls is OPTIONAL — include it ONLY when you need to take action on the internet
 // (send email, search, create issue, update CRM, etc). Max 5 calls per turn.
 // Every tool_call MUST be a real need, not filler. Omit the field entirely when no action needed.}"""

REQUIRED_KEYS = ("phase", "acknowledgment", "refreshed_open_question", "state_summary", "signals")
VALID_PHASES = ("exploring", "naming", "ready_to_act", "acting", "checking_in")
VALID_MODES = ("answer", "decide", "plan", "advice")

CONFIRM_SYSTEM = """You are the final quality gate for a founder's coach-and-brain assistant. A draft reply has been written.
Your ONLY job: make it undeniable.

Step 1 — TRUE REPLY CHECK. Read the founder's message. Does the draft genuinely answer what they actually asked?
If the draft dodges, generalizes, or answers a different question — the draft FAILS. It must directly, specifically
address their demand.

Step 2 — BEST POSSIBLE CHECK. Is this the genuinely best reply this founder could receive right now? The best reply is:
sharp, concrete, personal to their situation, free of fluff, and gives them something they can act on. If the draft has
even a hint of generic filler, weak phrasing, or a better answer exists — IMPROVE it.

Step 3 — REWRITE FOR CONNECTION. The trust is FELT in the tone, never stated. Rewrite so the voice is warm,
direct, a little magnetic — like the sharpest, most loyal person in their life. Simple powerful sentences.
The relationship is in how you say it, never in what you say about it.

STRICT RULES:
- NEVER use the word "friend". NEVER say "I'm on your side", "I've got your back", "we're in this together",
  "I'm in your corner", "as your friend", "you can count on me", "trust me".
- Keep facts, numbers, and specifics from the draft exactly as they are. Only upgrade tone and sharpness.
- End in a way that leaves them feeling capable.
- If the draft already passes all three checks, return it nearly verbatim.

Output STRICT JSON only:
{"verdict": "kept" | "improved", "reply": "<final reply text>"}"""


def _dedash(s: str) -> str:
    """Clean em-dashes -> comma without a stray leading space (slop ban + polish fix)."""
    s = s.replace(" — ", ", ").replace(" – ", ", ").replace("—", ", ").replace("–", ", ")
    return s.replace(" ,", ",")


def _confirm_final_reply(reply: str, user_msg: str, objective: str = "") -> str:
    """Confirmation layer: verify the draft truly answers the founder's demand, check it is the
    genuinely best possible reply, and rewrite it with a connected, attractive tone.
    NEVER blocks a turn — on any failure the original draft is returned unchanged."""
    if not (reply or "").strip():
        return reply or ""
    try:
        prompt = (
            f"FOUNDER'S GOAL: {objective or '(not yet stated)'}\n\n"
            f"FOUNDER JUST SAID: \"{user_msg}\"\n\n"
            f"DRAFT REPLY TO CONFIRM:\n{reply}\n\n"
            "Run the three checks now and output the verdict + final reply as STRICT JSON."
        )
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1600,
                                     system=[{"type": "text", "text": CONFIRM_SYSTEM}],
                                     thinking={"type": "disabled"},
                                     messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        out = json.loads(_extract_json(txt))
        final = _dedash(out.get("reply", "")).strip()
        if not final:
            return reply
        verdict = (out.get("verdict") or "").strip().lower()
        log.info(f"confirm layer verdict: {verdict}")
        return final
    except Exception as e:
        log.warning(f"confirm layer failed (keeping draft): {e}")
        return reply

# Run the single engine LLM call and normalize output
def llm_turn(thread: dict, substrate: dict, user_msg: str, intent: str, mode: str = "normal",
             attachment=None, user_doc=None,
             recall_block: str = "", attachment_preview=None,
             understanding=None, org_id: str = None):
    adjust_note = ""
    if intent == "action_adjust":
        adjust_note = ("ADJUSTMENT: the user is pushing back on the PRIOR NEXT ACTION above - "
                       "their message holds an obstacle or their own version of the step. Do not mark it done. "
                       "Recalibrate: keep what works about it, redesign it around their input. "
                       "The refreshed_next_action must visibly incorporate their words.\n")
    # Server may have pre-extracted the attachment via doc_memory (preferred path: handles all formats
    # + decides inline-vs-tree). Fall back to the legacy internal extractor if no preview was supplied.
    if attachment_preview is not None:
        vision_blocks = attachment_preview.get("vision_blocks") or []
        file_text = attachment_preview.get("inline_text") or ""
    else:
        vision_blocks, file_text = build_attachment_blocks(attachment)
    # Saved file snapshot from a prior turn (set when the user attached a file earlier).
    # Inject so the engine reasons on what it already saw, without the user re-uploading.
    saved_facts = (thread.get("current_file_facts") or "").strip()
    facts_block = f"\nFILE_FACTS (from a file the user attached earlier — still valid this turn):\n{saved_facts}\n" if saved_facts else ""
    user_ctx_block = _user_context_block(user_doc)
    # Living memory of this person (the "understanding trail"), injected so the engine remembers
    # across turns and threads and never re-asks what it already knows.
    _u = understanding if isinstance(understanding, dict) else {}
    _u_keys = ("focus", "fears", "blockers", "constraints", "tried", "motivators",
               "stage", "gap_to_goal", "emotional_read", "needs_now")
    _u_lines = [f"- {k}: {_u[k]}" for k in _u_keys if isinstance(_u.get(k), str) and _u.get(k).strip()]
    understanding_block = ("What I know about them (my living memory, update it this turn):\n"
                           + "\n".join(_u_lines) + "\n") if _u_lines else ""
    company_state_block = ""
    if user_doc and user_doc.get("id"):
        try:
            company_state_block = _get_state_block(user_doc["id"])
            if company_state_block:
                company_state_block += "\n"
        except Exception:
            pass
    prior_phase = (thread.get("current_phase") or "").strip() or "(none — this is an early turn)"
    geo = thread.get("user_geo") or {}
    geo_line = ""
    city, country = geo.get("city"), geo.get("country")
    if city and country and city not in ("Unknown", "Local"):
        geo_line = f"USER_LOCATION: {city}, {country} (anchor tool/platform/payment/regulation suggestions to here)\n"
    # Factory Bridge: if chat message is a business idea, build inline + inject evidence block
    factory_block = ""
    factory_artifact = None
    try:
        from factory_bridge import looks_like_business_idea, build_from_idea
        if org_id and looks_like_business_idea(user_msg):
            fb = build_from_idea(user_msg, org_id=org_id, user_id=(user_doc or {}).get("id", ""))
            if fb.get("ok"):
                factory_artifact = fb
                brand = (fb.get("catalog", {}) or {}).get("brand", {}) or {}
                worth = fb.get("worth", {}) or {}
                growth = fb.get("growth", {}) or {}
                factory_block = (
                    "FACTORY_BUILT (`build_from_idea` executed this turn — evidence, not speculation):\n"
                    f"- Build: {fb.get('id')} | idea: \"{fb.get('idea','')[:120]}\"\n"
                    f"- Brand: {brand.get('name','')} — {brand.get('tagline','')}\n"
                    f"- Worth: AOV ₹{worth.get('aov_inr','')} | margin {worth.get('margin','')} | valuation {worth.get('valuation_multiple','')}×\n"
                    f"- Growth headline: {growth.get('headline','')[:180]}\n"
                    "- The user asked to build a business — they now HAVE one. Do NOT ask for the idea again.\n"
                    "- Your job this turn: celebrate + explain what's built + the 3 immediate next actions from the growth plan. Link to /builder and /admin.\n"
                )
    except Exception:
        pass
    recall_section = (recall_block.strip() + "\n") if recall_block and recall_block.strip() else ""
    mcp_tools_section = _mcp_tools_block()  # Ch.X: inject available MCP tools into prompt
    # Wire 3: root cause context when user mentions business symptoms
    root_cause_section = ""
    workflow_section = ""
    org_id = user_doc.get("org_id") if user_doc else None
    if org_id:
        try:
            from business_system import root_cause_context_block
            root_cause_section = root_cause_context_block(org_id, user_msg)
            if root_cause_section:
                root_cause_section = root_cause_section + "\n\n"
        except Exception:
            pass
        try:
            from execution.workflows import suggest_workflow_block
            workflow_section = suggest_workflow_block(user_msg, org_id)
            if workflow_section:
                workflow_section = workflow_section + "\n\n"
        except Exception:
            pass
    brain_context_section = ""
    if org_id:
        try:
            brain_context_section = _brain_context_block(org_id, user_doc, user_msg)
        except Exception:
            pass
    # ── SALAAR inline: scan for threats, inject context into prompt ──
    salaar_block = ""
    try:
        from salaar.inline import salaar_inline_scan, salaar_auto_execute
        scan = salaar_inline_scan(user_msg, thread, user_doc)
        salaar_block = scan.get("context_block", "")
        if salaar_block:
            salaar_block = salaar_block + "\n"
        # Trigger L1-L2 auto-execution in background
        if scan.get("threats") and org_id:
            # ponytail: fire-and-forget — don't block the turn on execution
            try:
                salaar_auto_execute(org_id, user_doc.get("id", ""), scan["threats"])
            except Exception:
                pass
    except Exception:
        pass  # SALAAR is advisory — never block a turn on SALAAR failure
    prompt = (
        f"{user_ctx_block}"
        f"{understanding_block}"
        f"{geo_line}"
        f"Their goal: {thread['goal']}\n"
        f"What this means to them (their own words): {thread.get('why_now', '(not stated)')}\n"
        f"Where they are right now:\n{thread['current_state_summary']}\n"
        f"The question they're sitting with: {thread['current_open_question']}\n"
        f"The easiest path forward: {thread['current_easiest_path']}\n"
        f"The last action they committed to (check if it's done): {thread['current_next_action']}\n"
        f"Conversation stage: {prior_phase}\n"
        f"How they're doing: temperature={substrate['emotional_temperature']} consistency={substrate['execution_consistency']} pace={substrate['pace_calibration']} streak={substrate.get('streak', 0)} actions kept in a row\n"
        f"What this message feels like: {intent}\n"
        f"{adjust_note}"
        f"{facts_block}"
        f"{recall_section}"
        f"{mcp_tools_section}"
        f"{company_state_block}"
        f"{root_cause_section}"
        f"{workflow_section}"
        f"{brain_context_section}"
        f"{_bio_block(user_msg)}"
        f"{salaar_block}"
        f"{factory_block}"
        f"Their message: {user_msg}"
        f"{file_text}"
    )
    user_content = vision_blocks + [{"type": "text", "text": prompt}] if vision_blocks else prompt
    # Routing:
    #  ultra              -> Fable 5 (deep thinking) then Opus then Haiku
    #  file/recall present -> Sonnet 4.5 (cheaper, same context, great at analysis) then Opus then Haiku
    #  normal              -> Opus 4.8 then Haiku
    has_file_context = bool(vision_blocks) or bool(file_text) or bool(recall_section)
    if mode == "ultra":
        chain = (ULTRA_MODEL, PRIMARY_MODEL, FALLBACK_MODEL)
    elif has_file_context:
        chain = (ANALYTICAL_MODEL, PRIMARY_MODEL, FALLBACK_MODEL)
    else:
        chain = (PRIMARY_MODEL, FALLBACK_MODEL)
    last_err = None
    # System block is cached: SYSTEM is large and identical across turns, prompt caching cuts
    # ~90% off its repeated read cost from the 2nd turn onward (same model + same content).
    system_blocks = [{"type": "text", "text": SYSTEM,
                      "cache_control": {"type": "ephemeral"}}]
    for model in chain:
        try:
            kwargs = {"model": model, "max_tokens": 8000, "system": system_blocks,
                      "messages": [{"role": "user", "content": user_content}]}
            if has_file_context and model != ULTRA_MODEL:
                kwargs["max_tokens"] = 8000  # room for richer analysis on file/recall turns
            if model == ULTRA_MODEL:
                kwargs["max_tokens"] = 8000  # room for thinking + JSON output
                kwargs["thinking"] = {"type": "adaptive"}
                kwargs["extra_body"] = {"output_config": {"effort": "high"}}
            else:
                # DeepSeek reasoning models burn the whole budget on hidden chain-of-thought,
                # returning empty content. Disable thinking: the SYSTEM already demands a
                # structured REASONING SWEEP inside the JSON output.
                kwargs["thinking"] = {"type": "disabled"}
            r = client().messages.create(**kwargs)
            txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
            out = json.loads(_extract_json(txt))
            if not all(k in out for k in REQUIRED_KEYS):
                raise ValueError("incomplete JSON keys")
            # phase guardrails: clamp invalid phases, enforce null-fields by phase, enforce
            # single-question rule, strip em-dashes from voice-bearing fields.
            phase = (out.get("phase") or "exploring").strip().lower()
            if phase not in VALID_PHASES:
                phase = "exploring"
            out["phase"] = phase
            # Pre-action phases must not ship an action / payoff / big_picture / outbox
            if phase in ("exploring", "naming"):
                out["refreshed_next_action"] = None
                out["action_payoff"] = None
                out["big_picture_link"] = None
                out["outbox_alternative"] = None
                if phase == "exploring":
                    out["refreshed_easiest_path"] = None
            # If there's no concrete action, an outbox alternative makes no sense either.
            if not (out.get("refreshed_next_action") or "").strip():
                out["outbox_alternative"] = None
            for k in ("acknowledgment", "mirror", "insight", "refreshed_easiest_path",
                      "refreshed_next_action", "outbox_alternative", "action_payoff",
                      "big_picture_link", "bold_move", "refreshed_open_question", "state_summary"):
                v = out.get(k)
                if isinstance(v, str):
                    out[k] = _dedash(v)
            # insight removed from UI (no boxes); keep harmless default if a model still emits it
            if not isinstance(out.get("insight"), str):
                out["insight"] = ""
            # understanding trail must be a dict (living memory, persisted across turns)
            if not isinstance(out.get("understanding"), dict):
                out["understanding"] = {}
            # ── Merged brain fields: mode / recommendation / plan / citations / prediction ──
            mode_tag = str(out.get("mode") or "advice").strip().lower()
            out["mode"] = mode_tag if mode_tag in VALID_MODES else "advice"
            out["key_takeaway"] = _dedash(out.get("key_takeaway", "")) if isinstance(out.get("key_takeaway"), str) else ""
            if not (out.get("key_takeaway") or "").strip():
                out["key_takeaway"] = (out.get("acknowledgment") or "").strip()[:160]
            _rec = out.get("recommendation")
            out["recommendation"] = _dedash(_rec) if (out["mode"] == "decide" and isinstance(_rec, str) and _rec.strip()) else None
            _pl = out.get("plan")
            out["plan"] = [_dedash(s) for s in _pl if isinstance(s, str) and s.strip()][:8] if (out["mode"] == "plan" and isinstance(_pl, list)) else None
            if out["mode"] == "plan" and not out["plan"]:
                out["plan"] = [_dedash(out["acknowledgment"])[:400]]
            cits = out.get("citations")
            out["citations"] = [{"doc": str(c.get("doc", ""))[:200], "chapter": str(c.get("chapter", ""))[:200]}
                                for c in cits if isinstance(c, dict) and (c.get("doc") or c.get("chapter"))][:8] if isinstance(cits, list) else []
            out["found_in_docs"] = bool(out.get("found_in_docs")) if out["citations"] else False
            _po = out.get("predicted_outcome")
            if isinstance(_po, dict) and isinstance(_po.get("claim"), str) and _po["claim"].strip():
                try:
                    _conf = max(0, min(100, int(_po.get("confidence"))))
                except Exception:
                    _conf = 50
                try:
                    _days = max(1, min(90, int(_po.get("review_after_days"))))
                except Exception:
                    _days = 14
                out["predicted_outcome"] = {"claim": _dedash(_po["claim"])[:400], "confidence": _conf, "review_after_days": _days}
            else:
                out["predicted_outcome"] = None
            _dfi = out.get("dont_follow_if")
            out["dont_follow_if"] = _dedash(_dfi) if (isinstance(_dfi, str) and _dfi.strip()) else None
            # reasoning sweep: normalize to dict with defaults
            _rs = out.get("reasoning")
            out["reasoning"] = _rs if isinstance(_rs, dict) else {}
            # benchmark_facts: only real stated numbers
            _bf = out.get("benchmark_facts")
            if isinstance(_bf, dict) and isinstance(_bf.get("facts"), list):
                _facts = []
                for f in _bf["facts"]:
                    if isinstance(f, dict) and isinstance(f.get("metric"), str) and f["metric"].strip():
                        try:
                            _val = float(f.get("value"))
                        except Exception:
                            continue
                        _facts.append({"metric": f["metric"].strip()[:60], "value": _val,
                                       "unit": str(f.get("unit") or "")[:20]})
                out["benchmark_facts"] = {"industry": str(_bf.get("industry") or "")[:60], "facts": _facts[:10]}
            else:
                out["benchmark_facts"] = {"industry": "", "facts": []}
            # Enforce ONE question per turn: strip stray '?' from non-question fields.
            for k in ("acknowledgment", "mirror"):
                if isinstance(out.get(k), str):
                    out[k] = out[k].replace("?", ".")
            usage = {"input_tokens": int(getattr(r.usage, "input_tokens", 0) or 0),
                     "output_tokens": int(getattr(r.usage, "output_tokens", 0) or 0)}
            # ---- Ch.X: MCP tool execution ----
            tool_calls = out.get("tool_calls") if isinstance(out.get("tool_calls"), list) else []
            execution_results = None
            if tool_calls:
                try:
                    from execution.mcp_client import mcp_enabled
                    if mcp_enabled():
                        from execution.dispatcher import execute_plan as _exec_plan
                        plan = {"goal": thread.get("goal", ""), "actions": [
                            {"tool": tc.get("tool", ""), "args": tc.get("args", {}),
                             "depends_on": [], "description": tc.get("reason", tc.get("tool", ""))}
                            for tc in tool_calls[:5] if isinstance(tc, dict) and tc.get("tool")
                        ]}
                        if plan["actions"]:
                            exec_result = _exec_plan(plan, "general", org_id=org_id)
                            execution_results = exec_result.get("actions", [])
                            # Inject results into acknowledgment
                            done_actions = [a for a in execution_results if a.get("status") == "done"]
                            failed_actions = [a for a in execution_results if a.get("status") == "failed"]
                            summary_lines = []
                            for a in done_actions:
                                desc = a.get("description", a.get("tool", ""))
                                result_text = (a.get("result") or "")[:200]
                                summary_lines.append(f"✓ {desc}: {result_text}" if result_text else f"✓ {desc}: done")
                            for a in failed_actions:
                                summary_lines.append(f"✗ {a.get('description', a.get('tool', ''))}: {a.get('error', 'failed')}")
                            if summary_lines:
                                out["acknowledgment"] += "\n\n" + "\n".join(summary_lines)
                            # Wire 2: enqueue executed actions as tasks for tracking + learning
                            if org_id:
                                try:
                                    from execution.bridge import enqueue_engine_action
                                    for tc in tool_calls[:3]:
                                        enqueue_engine_action(org_id, {
                                            "description": tc.get("reason", tc.get("tool", "AI action")),
                                            "capability": tc.get("capability", "general"),
                                            "tool": tc.get("tool", ""),
                                            "args": tc.get("args", {}),
                                            "expected_outcome": tc.get("reason", "Action completed"),
                                            "reversibility": "REVERSIBLE",
                                        }, user_id=user_doc.get("id") if user_doc else None)
                                except Exception:
                                    pass
                except Exception as exec_err:
                    log.warning(f"MCP tool execution failed (non-fatal): {exec_err}")
            out["_execution"] = execution_results
            if factory_artifact is not None:
                out["factory_build"] = factory_artifact
                out["_reasoning"]["assumptions_detected"] = []
            goal = ""
            try:
                goal = (thread or {}).get("goal") or (substrate or {}).get("objective") or ""
            except Exception:
                pass
            out["acknowledgment"] = _confirm_final_reply(out["acknowledgment"], user_msg, goal)
            return out, model, usage
        except Exception as e:
            last_err = e
    raise RuntimeError(f"All models failed: {last_err}")


# ---------------------------------------------------------------- Ch.X: MCP tool-aware turns
def llm_turn_with_tools(thread: dict, substrate: dict, user_msg: str, intent: str,
                        mode: str = "normal", attachment=None, user_doc=None,
                        recall_block: str = "", attachment_preview=None,
                        understanding=None, department_function: str = "general",
                        org_id: str = None, user_id: str = None):
    """Execute an LLM turn with MCP tool access. When the LLM requests a tool call,
    execute it via the Composio dispatcher, feed the result back, and return a
    natural-language reply. MCP is infrastructure — reasoning stays in SALAAR."""
    from execution.mcp_client import mcp_enabled

    if not mcp_enabled():
        return llm_turn(thread, substrate, user_msg, intent, mode,
                        attachment, user_doc, recall_block, attachment_preview, understanding)

    out, model, usage = llm_turn(thread, substrate, user_msg, intent, mode,
                                  attachment, user_doc, recall_block,
                                  attachment_preview, understanding)
    return out, model, usage


def execute_tool_plan(plan: dict, department_function: str = "general",
                      thread_id: str = None, user_id: str = None, org_id: str = None) -> dict:
    """Execute a tool plan extracted from an LLM response. Bridge from engine to dispatcher."""
    from execution.dispatcher import execute_plan as _execute_plan, validate_plan
    from execution.collector import collect_execution_result, execution_summary

    issues = validate_plan(plan)
    if issues:
        return {"error": "plan_validation_failed", "issues": issues}

    result = _execute_plan(plan, department_function)
    evidence = []
    for action in (result.get("actions") or []):
        ev = collect_execution_result(action, thread_id=thread_id,
                                       user_id=user_id, org_id=org_id)
        evidence.append(ev)

    result["evidence"] = evidence
    result["execution_summary"] = execution_summary(evidence)
    return result
