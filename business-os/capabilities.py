"""Universal Capability Platform — spec → artifact → deploy → iterate → track.
Replaces builder.py. Handles websites, reports, campaigns, automations, docs, and more.

Architecture:
  Founder: "I need X"
  → Capability Router: identifies type (website|report|campaign|...)
  → Spec Generator: LLM produces structured spec (type-aware prompt)
  → Artifact Generator: LLM produces the actual deliverable
  → Deploy Connector: pushes to the right platform
  → Iteration Loop: feedback → regenerate → redeploy
  → Outcome Tracker: measures real business impact

Each capability = {type, spec_prompt, artifact_prompt, deploy_platform, trigger_kw, metrics}
"""
import json
import uuid
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from llm_client import client as llm_client, _extract_json, ULTRA_MODEL

log = logging.getLogger("capabilities")

# In-memory store of active capability builds
BUILDS = {}  # in-memory store for active builds (persist to DB for production)


def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# Capability Registry — 15 types, extensible
# ======================================================================

# Registry of all capability types with prompts and deploy configs
CAPABILITIES = {
    "website": {
        "label": "Website / Landing Page",
        "description": "Generate and deploy a complete website",
        "trigger_kw": ["build", "website", "landing page", "create site", "make a site", "web page", "homepage", "landing"],
        "spec_prompt": """You design a website specification from the founder's description.
Return ONLY JSON:
{"site_name": "...", "tagline": "...",
 "sections": [{"type": "hero|features|testimonials|pricing|cta|footer|about|custom", "title": "...", "content": "...", "elements": [...]}],
 "colors": {"primary": "#hex", "secondary": "#hex", "bg": "#hex", "text": "#hex"},
 "cta_text": "...", "cta_url": "..."}""",
        "artifact_prompt": """You are a senior frontend engineer. Generate a COMPLETE, production-ready single-file HTML website.
Inline CSS. Mobile-responsive. Modern design. No frameworks. Max 500 lines.
All CSS inline in <style>. All images use placeholder divs or unsplash URLs.
All CTAs link to #cta. Include SEO meta tags.
Return ONLY JSON: {"html": "the complete HTML string"}""",
        "deploy_platform": "github",
        "deploy_fn": "_deploy_to_github",
        "output_format": "html",
        "metrics": ["traffic", "conversion_rate", "time_on_page"],
    },
    "report": {
        "label": "Report / Analysis",
        "description": "Generate a structured business report",
        "trigger_kw": ["report", "analysis", "analytics report", "monthly report", "quarterly", "summary", "write up"],
        "spec_prompt": """You structure a business report from the founder's request.
Return ONLY JSON:
{"title": "...", "audience": "...", "sections": [{"heading": "...", "content_type": "summary|data|chart|recommendation", "key_points": [...]}],
 "data_needed": ["specific data points to include"], "tone": "formal|casual|investor_ready"}""",
        "artifact_prompt": """You write a professional business report. Clear, concise, data-driven.
Format in Markdown with headers, bullet points, and tables where appropriate.
Include an executive summary, key findings, data analysis, and actionable recommendations.
Return ONLY JSON: {"markdown": "the complete report in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["decisions_made", "actions_taken", "stakeholder_feedback"],
    },
    "email_campaign": {
        "label": "Email Campaign",
        "description": "Design and send an email campaign",
        "trigger_kw": ["email campaign", "newsletter", "email blast", "drip", "welcome email", "send email to", "broadcast"],
        "spec_prompt": """You design an email campaign strategy.
Return ONLY JSON:
{"campaign_name": "...", "audience": "...", "goal": "...",
 "emails": [{"subject": "...", "body_outline": "...", "cta": "...", "delay_days": 0}]}""",
        "artifact_prompt": """You write a complete marketing email. Engaging subject line. Clear, warm body.
Personalized where possible. One clear CTA. No spam triggers.
Return ONLY JSON: {"subject": "...", "body": "the complete email HTML"}""",
        "deploy_platform": "gmail",
        "deploy_fn": "_deploy_to_gmail",
        "output_format": "html",
        "metrics": ["open_rate", "click_rate", "conversions"],
    },
    "investor_deck": {
        "label": "Investor Deck",
        "description": "Generate an investor presentation",
        "trigger_kw": ["deck", "pitch deck", "investor presentation", "fundraise deck", "pitch"],
        "spec_prompt": """You structure a startup pitch deck following Sequoia's framework.
Return ONLY JSON:
{"company_name": "...", "one_liner": "...",
 "slides": [{"title": "...", "key_message": "...", "data_points": [...], "visual_idea": "..."}],
 "target_raise": "...", "use_of_funds": "..."}""",
        "artifact_prompt": """You write the content for each pitch deck slide. Concise, punchy, data-backed.
One key message per slide. Numbers over claims. Social proof where relevant.
Return ONLY JSON: {"slides": [{"title": "...", "body": "...", "speaker_notes": "..."}]}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "text",
        "metrics": ["funding_raised", "investor_meetings", "term_sheets"],
    },
    "automation": {
        "label": "Workflow Automation",
        "description": "Design a business automation workflow",
        "trigger_kw": ["automate", "workflow", "zapier", "automation", "auto", "trigger", "integrate"],
        "spec_prompt": """You design a business automation workflow.
Return ONLY JSON:
{"name": "...", "trigger": {"app": "...", "event": "..."},
 "steps": [{"app": "...", "action": "...", "data_mapping": "..."}],
 "expected_outcome": "..."}""",
        "artifact_prompt": """You write a detailed automation setup guide with step-by-step instructions.
Include: triggers, actions, data mapping, testing steps, error handling.
Return ONLY JSON: {"guide": "complete setup guide in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["tasks_automated", "time_saved_hrs", "error_reduction"],
    },
    "contract": {
        "label": "Legal Contract",
        "description": "Draft a legal document or contract",
        "trigger_kw": ["contract", "agreement", "NDA", "terms", "legal", "MOU", "service agreement", "terms of service"],
        "spec_prompt": """You structure a legal document.
Return ONLY JSON:
{"document_type": "...", "parties": [...], "key_terms": [...],
 "sections": [{"title": "...", "content_outline": "..."}],
 "jurisdiction": "..."}""",
        "artifact_prompt": """You draft a professional legal document. Clear language. Comprehensive clauses.
Include standard sections: parties, recitals, definitions, terms, term and termination, governing law.
IMPORTANT: Add disclaimer at top: "THIS IS A DRAFT. REVIEW BY A QUALIFIED ATTORNEY BEFORE USE."
Return ONLY JSON: {"document": "the complete document in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["contracts_executed", "legal_issues_avoided"],
    },
    "job_description": {
        "label": "Job Description",
        "description": "Generate a structured job description",
        "trigger_kw": ["job", "hiring", "job description", "JD", "role description", "job post", "job posting"],
        "spec_prompt": """You structure a job description.
Return ONLY JSON:
{"role": "...", "department": "...", "level": "...",
 "requirements": {"must_have": [...], "nice_to_have": [...]},
 "outcomes": ["3-5 measurable outcomes for first 6 months"]}""",
        "artifact_prompt": """You write a compelling job description. Clear outcomes, not responsibilities.
Culture-fit indicators. Growth trajectory. Compensation range if provided.
Return ONLY JSON: {"description": "the complete JD in markdown", "linkedin_summary": "200-char summary"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["applicants", "qualified_candidates", "time_to_hire"],
    },
    "social_campaign": {
        "label": "Social Media Campaign",
        "description": "Plan and draft a social media campaign",
        "trigger_kw": ["social media", "posts", "content calendar", "social campaign", "Instagram", "LinkedIn post"],
        "spec_prompt": """You plan a social media campaign.
Return ONLY JSON:
{"campaign_name": "...", "platforms": [...], "duration_days": 0,
 "posts": [{"platform": "...", "content_type": "image|video|text|carousel", "hook": "...", "body": "...", "cta": "..."}]}""",
        "artifact_prompt": """You write individual social media posts. Platform-native style.
Short, punchy. Emojis where appropriate. Hashtags. Engagement hooks.
Return ONLY JSON: {"posts": [{"platform": "...", "text": "...", "hashtags": [...], "image_idea": "..."}]}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "text",
        "metrics": ["engagement", "reach", "followers_gained"],
    },
    "product_spec": {
        "label": "Product Specification",
        "description": "Generate a PRD or product spec",
        "trigger_kw": ["spec", "PRD", "product spec", "feature spec", "requirements", "write a spec"],
        "spec_prompt": """You structure a product specification document.
Return ONLY JSON:
{"product_name": "...", "problem": "...", "target_user": "...",
 "features": [{"name": "...", "priority": "P0|P1|P2", "user_story": "...", "acceptance_criteria": [...]}],
 "success_metrics": [...], "timeline": "..."}""",
        "artifact_prompt": """You write a comprehensive product specification. Clear problem statement.
Prioritized features with user stories and acceptance criteria. Success metrics. Timeline.
Return ONLY JSON: {"spec": "the complete PRD in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["features_built", "spec_accuracy", "dev_velocity"],
    },
    "onboarding_doc": {
        "label": "Onboarding Document",
        "description": "Generate employee or customer onboarding docs",
        "trigger_kw": ["onboarding", "welcome doc", "getting started guide", "setup guide", "employee handbook"],
        "spec_prompt": """You structure an onboarding document.
Return ONLY JSON:
{"type": "employee|customer", "sections": [{"title": "...", "content_type": "guide|checklist|policy|reference"}],
 "key_outcomes": ["what the person should know/do after onboarding"], "timeline": "..."}""",
        "artifact_prompt": """You write a comprehensive onboarding document. Warm, welcoming tone.
Clear step-by-step instructions. Checklists. Links to resources. Expected outcomes.
Return ONLY JSON: {"document": "the complete document in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["time_to_productivity", "satisfaction_score", "retention"],
    },
    "dashboard": {
        "label": "Dashboard / Analytics View",
        "description": "Define and generate a business dashboard spec",
        "trigger_kw": ["dashboard", "metrics board", "KPI dashboard", "analytics view", "reporting view"],
        "spec_prompt": """You design a business dashboard specification.
Return ONLY JSON:
{"name": "...", "audience": "...",
 "widgets": [{"type": "number|chart|table|funnel", "metric": "...", "data_source": "...", "refresh": "realtime|daily|weekly"}],
 "layout": "grid columns description"}""",
        "artifact_prompt": """You write a detailed dashboard specification including SQL/query hints, data sources, refresh schedules, and access controls.
Return ONLY JSON: {"spec": "complete dashboard spec in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["decisions_informed", "time_saved_reporting"],
    },
    "api_endpoint": {
        "label": "API Endpoint",
        "description": "Generate API endpoint code and schema",
        "trigger_kw": ["API", "endpoint", "backend code", "create API", "microservice", "REST endpoint"],
        "spec_prompt": """You design an API endpoint specification.
Return ONLY JSON:
{"name": "...", "method": "GET|POST|PUT|DELETE", "path": "...",
 "request": {"params": [...], "body_schema": {...}},
 "response": {"schema": {...}, "error_codes": [...]},
 "auth": "none|api_key|jwt"}""",
        "artifact_prompt": """You write production-ready backend code for the API endpoint. 
Include input validation, error handling, auth middleware, and tests.
Return ONLY JSON: {"code": "the complete Python/FastAPI implementation"}""",
        "deploy_platform": "github",
        "deploy_fn": "_deploy_to_github",
        "output_format": "code",
        "metrics": ["uptime", "latency_p95", "error_rate"],
    },
    "blog_post": {
        "label": "Blog Post / Article",
        "description": "Write a complete blog post or article",
        "trigger_kw": ["blog", "article", "write about", "thought leadership", "guest post"],
        "spec_prompt": """You structure a blog post outline.
Return ONLY JSON:
{"title": "...", "meta_description": "...", "target_keyword": "...",
 "sections": [{"heading": "...", "key_points": [...], "word_count": 0}],
 "tone": "professional|conversational|technical", "cta": "..."}""",
        "artifact_prompt": """You write a complete, engaging blog post. Strong hook in the intro. 
Each section delivers on its promise. Data and examples where relevant. Natural keyword inclusion.
Return ONLY JSON: {"title": "...", "content": "the complete post in markdown", "meta_description": "..."}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["reads", "shares", "leads_generated"],
    },
    "financial_model": {
        "label": "Financial Model",
        "description": "Generate a financial projection or model",
        "trigger_kw": ["financial model", "projection", "forecast", "P&L", "revenue model", "unit economics"],
        "spec_prompt": """You design a financial model structure.
Return ONLY JSON:
{"model_name": "...", "timeframe_months": 0,
 "revenue_streams": [{"name": "...", "pricing_model": "...", "assumptions": [...]}],
 "cost_categories": [{"name": "...", "type": "fixed|variable", "assumptions": [...]}],
 "key_metrics": ["ARR", "gross_margin", "burn_rate", "runway"]}""",
        "artifact_prompt": """You write a detailed financial model specification including all assumptions, formulas, and growth drivers.
The spec should be detailed enough that someone could build the spreadsheet from it.
Return ONLY JSON: {"model": "the complete model spec in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["forecast_accuracy", "decisions_informed"],
    },
    "strategy_doc": {
        "label": "Strategy Document",
        "description": "Generate a strategic plan or memo",
        "trigger_kw": ["strategy", "strategic plan", "memo", "positioning doc", "competitive analysis"],
        "spec_prompt": """You structure a strategy document following Rumelt's kernel.
Return ONLY JSON:
{"title": "...", "diagnosis": "...", "guiding_policy": "...",
 "coherent_actions": [...], "success_metrics": [...],
 "risks": [...], "timeline": "..."}""",
        "artifact_prompt": """You write a sharp, actionable strategy document. Rumelt's kernel structure.
Clear diagnosis of the challenge. Guiding policy that rules things out. Coherent actions with owners and deadlines.
Return ONLY JSON: {"strategy": "the complete strategy doc in markdown"}""",
        "deploy_platform": "notion",
        "deploy_fn": "_deploy_to_notion",
        "output_format": "markdown",
        "metrics": ["strategic_clarity_score", "execution_alignment", "outcomes_achieved"],
    },
}


# ======================================================================
# Capability Router
# ======================================================================

def route_capability(user_message: str) -> Optional[dict]:
    """Identify which capability type a user message maps to.
    Prioritizes: 1) multi-word phrase matches, 2) longer keyword matches, 3) most matches."""
    msg_lower = user_message.lower()
    scored = []
    for ctype, cap in CAPABILITIES.items():
        score = 0
        for kw in cap["trigger_kw"]:
            if kw.lower() in msg_lower:
                # Multi-word phrases get double weight, longer keywords get higher base score
                word_count = len(kw.split())
                kw_length = len(kw)
                score += (2 if word_count > 1 else 1) * max(1, kw_length // 3)
        if score > 0:
            scored.append((score, ctype, cap))
    scored.sort(key=lambda x: -x[0])
    if scored:
        _, ctype, cap = scored[0]
        return {"type": ctype, **cap}
    return None


# ======================================================================
# Spec Generator
# ======================================================================

def generate_spec(capability_type: str, description: str) -> dict:
    """LLM: description → structured spec per capability type."""
    cap = CAPABILITIES.get(capability_type)
    if not cap:
        return {"error": f"Unknown capability: {capability_type}"}

    prompt = f"FOUNDER'S REQUEST:\n{description}\n\nGenerate a structured specification for: {cap['label']}"
    try:
        r = llm_client().messages.create(
            model=ULTRA_MODEL, max_tokens=2000,
            system=[{"type": "text", "text": cap["spec_prompt"]}],
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            extra_body={"output_config": {"effort": "high"}},
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"Spec generation failed for {capability_type}: {e}")
        return {"error": str(e)[:200]}


# ======================================================================
# Artifact Generator
# ======================================================================

def generate_artifact(capability_type: str, spec: dict, iteration_feedback: str = "") -> dict:
    """LLM: spec → complete deliverable."""
    cap = CAPABILITIES.get(capability_type)
    if not cap:
        return {"error": f"Unknown capability: {capability_type}"}

    spec_json = json.dumps(spec, ensure_ascii=False)[:3000]
    feedback_line = f"\nITERATION FEEDBACK: {iteration_feedback}" if iteration_feedback else ""
    prompt = f"SPECIFICATION:\n{spec_json}\n{feedback_line}\n\nGenerate the complete {cap['label']}."

    try:
        r = llm_client().messages.create(
            model=ULTRA_MODEL, max_tokens=8000,
            system=[{"type": "text", "text": cap["artifact_prompt"]}],
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            extra_body={"output_config": {"effort": "high"}},
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"Artifact generation failed for {capability_type}: {e}")
        return {"error": str(e)[:200]}


# ======================================================================
# Deploy Connectors
# ======================================================================

def _deploy_to_github(artifact: dict, name: str, commit_msg: str = "Generated by SmartDecigen") -> dict:
    """Push code/file to GitHub repo. Returns URL."""
    import base64, httpx
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not configured", "deployed": False}

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json",
               "Content-Type": "application/json"}

    # Get owner
    owner = os.environ.get("GITHUB_OWNER", "")
    if not owner:
        try:
            r = httpx.get("https://api.github.com/user", headers=headers, timeout=15)
            owner = r.json().get("login", "")
        except Exception:
            pass

    if not owner:
        return {"error": "GITHUB_OWNER not set", "deployed": False}

    full_repo = f"{owner}/{name}"
    html = artifact.get("html") or artifact.get("code") or json.dumps(artifact)
    content_b64 = base64.b64encode(html.encode("utf-8")).decode("utf-8")

    # Create repo
    try:
        r = httpx.get(f"https://api.github.com/repos/{full_repo}", headers=headers, timeout=15)
        if r.status_code == 404:
            httpx.post("https://api.github.com/user/repos", headers=headers,
                       json={"name": name, "auto_init": True, "private": False}, timeout=15)
    except Exception:
        pass

    # Push
    body = {"message": commit_msg, "content": content_b64, "branch": "main"}
    try:
        existing = httpx.get(f"https://api.github.com/repos/{full_repo}/contents/index.html",
                             headers=headers, timeout=15)
        if existing.status_code == 200:
            body["sha"] = existing.json().get("sha", "")
        httpx.put(f"https://api.github.com/repos/{full_repo}/contents/index.html",
                  headers=headers, json=body, timeout=30)
        return {"deployed": True, "url": f"https://{owner}.github.io/{name}/"}
    except Exception as e:
        return {"error": str(e)[:200], "deployed": False}


def _deploy_to_notion(artifact: dict, name: str, _: str = "") -> dict:
    """Create a Notion page from artifact text. Returns URL."""
    token = os.environ.get("NOTION_TOKEN", "")
    parent_id = os.environ.get("NOTION_PARENT_PAGE_ID", "")
    if not token or not parent_id:
        # Fallback: return artifact as text (founder can paste manually)
        content = artifact.get("markdown") or artifact.get("document") or artifact.get("strategy") or json.dumps(artifact)[:5000]
        return {"deployed": True, "fallback": "notion_config_missing",
                "content": content, "note": "NOTION_TOKEN and NOTION_PARENT_PAGE_ID not set. Content generated but not deployed."}

    import httpx
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
               "Notion-Version": "2022-06-28"}

    content = artifact.get("markdown") or artifact.get("document") or artifact.get("strategy") or artifact.get("spec") or ""

    # Simple text block — for full rich text, need more complex parsing
    body = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"text": {"content": name[:100]}}]},
        },
        "children": [{"object": "block", "type": "paragraph",
                      "paragraph": {"rich_text": [{"text": {"content": content[:2000]}}]}}],
    }

    try:
        r = httpx.post("https://api.notion.com/v1/pages", headers=headers, json=body, timeout=15)
        if r.status_code in (200, 201):
            page_id = r.json().get("id", "").replace("-", "")
            return {"deployed": True, "url": f"https://notion.so/{page_id}"}
        return {"error": f"Notion API {r.status_code}", "deployed": False, "content": content[:5000]}
    except Exception as e:
        return {"error": str(e)[:200], "deployed": False, "content": content[:5000]}


def _deploy_to_gmail(artifact: dict, name: str, _: str = "") -> dict:
    """Return artifact as draft email text (founder sends via Gmail connection)."""
    subject = artifact.get("subject", name)
    body = artifact.get("body", json.dumps(artifact)[:2000])
    return {"deployed": True, "draft": {"subject": subject, "body": body},
            "note": "Content ready. Send via Gmail connection or copy to send manually."}


# Map deploy connector names to implementations
DEPLOY_FUNCTIONS = {
    "_deploy_to_github": _deploy_to_github,
    "_deploy_to_notion": _deploy_to_notion,
    "_deploy_to_gmail": _deploy_to_gmail,
}


# ======================================================================
# Main Pipeline
# ======================================================================

def execute_capability(description: str, capability_type: str = None, deploy: bool = True) -> dict:
    """Full pipeline: route → spec → artifact → deploy."""
    build_id = f"cap_{uuid.uuid4().hex[:12]}"

    # Step 0: Route if not specified
    if not capability_type:
        route = route_capability(description)
        if not route:
            return {"build_id": build_id, "status": "failed", "step": "route", "error": "Could not identify capability type"}
        capability_type = route["type"]
        cap = route
    else:
        cap = CAPABILITIES.get(capability_type)
        if not cap:
            return {"build_id": build_id, "status": "failed", "step": "route", "error": f"Unknown capability: {capability_type}"}

    log.info(f"Capability {build_id}: type={capability_type}, desc='{description[:80]}'")

    # Step 1: Generate spec
    spec = generate_spec(capability_type, description)
    if spec.get("error"):
        return {"build_id": build_id, "status": "failed", "step": "spec", "error": spec["error"], "type": capability_type}

    # Step 2: Generate artifact
    artifact = generate_artifact(capability_type, spec)
    if artifact.get("error"):
        return {"build_id": build_id, "status": "failed", "step": "artifact", "error": artifact["error"], "spec": spec, "type": capability_type}

    # Step 3: Deploy
    deploy_result = {"deployed": False}
    if deploy:
        name = spec.get("site_name") or spec.get("title") or spec.get("campaign_name") or description.split()[-1].lower()
        name = name.lower().replace(" ", "-")[:40]
        deploy_fn = DEPLOY_FUNCTIONS.get(cap.get("deploy_fn", ""))
        if deploy_fn:
            deploy_result = deploy_fn(artifact, name, f"Generated: {description[:80]}")
        else:
            deploy_result = {"deployed": True, "note": f"No deploy connector for {cap['deploy_platform']}"}

    build = {
        "build_id": build_id,
        "type": capability_type,
        "label": cap["label"],
        "status": "deployed" if deploy_result.get("deployed") else "complete",
        "spec": spec,
        "artifact": {k: v[:500] if isinstance(v, str) and len(v) > 500 else v for k, v in artifact.items()},
        "url": deploy_result.get("url", ""),
        "deploy_platform": cap["deploy_platform"],
        "deploy_note": deploy_result.get("note", deploy_result.get("fallback", "")),
        "metrics": cap["metrics"],
        "error": deploy_result.get("error", ""),
        "created_at": _now().isoformat(),
    }

    BUILDS[build_id] = build
    return build


def iterate_capability(build_id: str, feedback: str) -> dict:
    """Iterate on an existing capability build."""
    build = BUILDS.get(build_id)
    if not build:
        return {"error": "Build not found"}

    ctype = build["type"]
    spec = build.get("spec", {})

    artifact = generate_artifact(ctype, spec, iteration_feedback=feedback)
    if artifact.get("error"):
        return {"status": "failed", "error": artifact["error"]}

    # Redeploy
    cap = CAPABILITIES.get(ctype, {})
    deploy_fn = DEPLOY_FUNCTIONS.get(cap.get("deploy_fn", ""))
    deploy_result = deploy_fn(artifact, spec.get("site_name", "update"), f"Iterate: {feedback[:80]}") if deploy_fn else {"deployed": True}

    build["artifact"] = {k: v[:500] if isinstance(v, str) and len(v) > 500 else v for k, v in artifact.items()}
    build["url"] = deploy_result.get("url", build.get("url", ""))
    build["status"] = "deployed" if deploy_result.get("deployed") else "complete"
    build["iteration_count"] = build.get("iteration_count", 0) + 1
    build["last_feedback"] = feedback[:200]

    return build


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    assert len(CAPABILITIES) == 15, f"Expected 15 capabilities, got {len(CAPABILITIES)}"
    for ctype, cap in CAPABILITIES.items():
        assert "spec_prompt" in cap, f"{ctype} missing spec_prompt"
        assert "artifact_prompt" in cap, f"{ctype} missing artifact_prompt"
        assert "trigger_kw" in cap, f"{ctype} missing trigger_kw"
        assert "deploy_fn" in cap, f"{ctype} missing deploy_fn"

    route = route_capability("build me a landing page for my skincare brand")
    assert route and route["type"] == "website", f"Expected website, got {route}"

    route2 = route_capability("I need an investor pitch deck for our Series A")
    assert route2 and route2["type"] == "investor_deck", f"Expected investor_deck, got {route2}"

    route3 = route_capability("write a job description for a senior engineer")
    assert route3 and route3["type"] == "job_description", f"Expected job_description, got {route3}"

    total_kw = sum(len(cap["trigger_kw"]) for cap in CAPABILITIES.values())
    print(f"OK — {len(CAPABILITIES)} capabilities, {total_kw} trigger keywords, router verified")
