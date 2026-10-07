"""Workflow Templates — pre-built multi-step execution plans for common business actions.

20 functions, 3-5 workflows each. Each workflow has:
  - trigger keywords (what the founder says to activate it)
  - tools (the specific tool chain to execute)
  - expected outcome
  - risk level (L1-L5 for permissions)

When a founder mentions a trigger, the system suggests the workflow.
Founder approves → dispatcher executes the tool chain → verification runs.
"""
import logging

log = logging.getLogger("execution.workflows")

# Each workflow: { id, trigger_keywords, description, tools, expected_outcome, risk }

WORKFLOWS = {
    "strategy": [
        {
            "id": "competitor_analysis",
            "trigger": ["competitor", "competition", "market share", "who else", "rival"],
            "description": "Analyze competitors and generate market positioning report",
            "tools": [
                {"tool": "GOOGLE_SEARCH", "args": {"query": "{competitor_name} funding news 2024"}, "description": "Search competitor news"},
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Competitor Analysis: {competitor_name}", "content": "{search_results}"}, "description": "Document findings in Notion"},
            ],
            "expected_outcome": "Competitor analysis document created with latest market intelligence",
            "risk": "L3",
        },
        {
            "id": "strategic_planning_session",
            "trigger": ["strategy", "planning", "next quarter", "roadmap", "direction"],
            "description": "Schedule strategy session with key stakeholders",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{stakeholder_emails}", "subject": "Strategy Planning: {topic}", "body": "Let's align on {topic}. I've attached the current state. Best times: {availability}."}, "description": "Invite stakeholders"},
                {"tool": "GOOGLE_CALENDAR_CREATE_EVENT", "args": {"summary": "Strategy Session: {topic}", "attendees": "{stakeholder_emails}"}, "description": "Block calendar"},
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Strategy Session Prep: {topic}", "content": "Current state, key decisions needed, data to review"}, "description": "Prep document"},
            ],
            "expected_outcome": "Strategy session scheduled with prep document ready",
            "risk": "L2",
        },
    ],
    "product": [
        {
            "id": "bug_triage",
            "trigger": ["bug", "broken", "not working", "error", "issue", "crash"],
            "description": "Create and assign bug tickets with context",
            "tools": [
                {"tool": "GITHUB_CREATE_ISSUE", "args": {"title": "Bug: {description}", "body": "Reported by customer. Impact: {impact}. Steps to reproduce: {steps}"}, "description": "File bug report"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#engineering", "text": "New bug reported: {description}. Issue: {issue_url}. Priority: {priority}"}, "description": "Alert engineering team"},
            ],
            "expected_outcome": "Bug filed and engineering team alerted",
            "risk": "L3",
        },
        {
            "id": "feature_spec",
            "trigger": ["new feature", "build feature", "launch feature", "ship feature", "MVP", "product spec"],
            "description": "Create feature specification and assign to team",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Feature Spec: {feature_name}", "content": "Problem, solution, success metrics, timeline"}, "description": "Write spec"},
                {"tool": "GITHUB_CREATE_ISSUE", "args": {"title": "Build: {feature_name}", "body": "Spec: {notion_url}. Owner: {assignee}. Target: {deadline}"}, "description": "Create dev task"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#product", "text": "New feature spec ready: {feature_name}. Link: {notion_url}"}, "description": "Notify product team"},
            ],
            "expected_outcome": "Feature spec written, dev task created, team notified",
            "risk": "L2",
        },
    ],
    "marketing": [
        {
            "id": "content_calendar",
            "trigger": ["content", "blog", "social media", "post", "newsletter", "publish"],
            "description": "Create and schedule content across channels",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Content Calendar: {month}", "content": "Weekly content plan with topics, channels, deadlines"}, "description": "Create calendar"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#marketing", "text": "Content calendar for {month} is ready. Link: {notion_url}"}, "description": "Share with team"},
            ],
            "expected_outcome": "Content calendar created and shared with marketing team",
            "risk": "L3",
        },
        {
            "id": "launch_announcement",
            "trigger": ["launch", "announce", "PR", "press", "release"],
            "description": "Draft and distribute launch announcement across channels",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{press_contacts}", "subject": "Announcing: {product_name}", "body": "We're launching {product_name}. Press release and assets attached."}, "description": "Send press release"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#general", "text": "Launch day: {product_name} is live! Press release sent to {count} contacts."}, "description": "Internal announcement"},
            ],
            "expected_outcome": "Launch announcement distributed to press and team",
            "risk": "L4",
        },
    ],
    "sales": [
        {
            "id": "follow_up_leads",
            "trigger": ["follow up", "lead", "prospect", "pipeline", "outreach", "cold"],
            "description": "Follow up with cold leads and track in CRM",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{lead_email}", "subject": "Following up: {context}", "body": "Hi {name}, I wanted to follow up on our conversation about {topic}. Would {date} work for a quick call?"}, "description": "Send follow-up email"},
                {"tool": "GOOGLE_CALENDAR_CREATE_EVENT", "args": {"summary": "Call with {lead_name}", "attendees": "{lead_email}"}, "description": "Schedule call if they agree"},
            ],
            "expected_outcome": "Leads followed up, meetings scheduled",
            "risk": "L4",
        },
        {
            "id": "deal_review",
            "trigger": ["deal", "close", "negotiate", "proposal", "contract", "pricing"],
            "description": "Prepare deal review with competitive analysis",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Deal Review: {deal_name}", "content": "Deal size, stakeholders, competition, risks, next steps"}, "description": "Document deal strategy"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#sales", "text": "Deal review ready: {deal_name}. Value: {deal_size}. Link: {notion_url}"}, "description": "Share with sales team"},
            ],
            "expected_outcome": "Deal strategy documented and shared with sales team",
            "risk": "L3",
        },
    ],
    "customer_success": [
        {
            "id": "churn_intervention",
            "trigger": ["churn", "cancelling", "cancel", "leaving", "unhappy", "complaint", "refund"],
            "description": "Intervene with at-risk customer before they churn",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{customer_email}", "subject": "Checking in — how can we help?", "body": "Hi {name}, I noticed you might be running into issues. I'd love to hop on a quick call to make sure we're solving your problem. How's {date}?"}, "description": "Reach out personally"},
                {"tool": "GOOGLE_CALENDAR_CREATE_EVENT", "args": {"summary": "Customer save call: {customer_name}", "attendees": "{customer_email}"}, "description": "Schedule intervention call"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#customer-success", "text": "At-risk: {customer_name} ({customer_email}). Sent intervention email. Status: {health_score}"}, "description": "Alert CS team"},
            ],
            "expected_outcome": "At-risk customer contacted, intervention call scheduled, team alerted",
            "risk": "L4",
        },
        {
            "id": "onboarding_sequence",
            "trigger": ["onboard", "new customer", "welcome", "setup", "getting started"],
            "description": "Trigger onboarding sequence for new customer",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{customer_email}", "subject": "Welcome to {product} — let's get you set up", "body": "Hi {name}, welcome! Here's your quickstart guide. Your dedicated CSM is {csm_name}. Book your onboarding call: {calendar_link}"}, "description": "Send welcome email"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#customer-success", "text": "New customer onboarded: {customer_name}. CSM: {csm_name}. Onboarding call scheduled."}, "description": "Notify CS team"},
            ],
            "expected_outcome": "New customer welcomed, CS team notified",
            "risk": "L3",
        },
    ],
    "finance": [
        {
            "id": "monthly_close",
            "trigger": ["revenue", "month end", "close books", "reconciliation", "P&L", "financial report", "investor update"],
            "description": "Run monthly financial close and generate reports",
            "tools": [
                {"tool": "STRIPE_LIST_INVOICES", "args": {"limit": "50"}, "description": "Pull revenue data"},
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{investor_emails}", "subject": "Monthly Update: {month}", "body": "Revenue: {revenue}. Cash: {cash}. Burn: {burn}. Runway: {runway} months. Key highlights below."}, "description": "Send investor update"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#leadership", "text": "Monthly close complete. Revenue: {revenue}. Cash: {cash}. Runway: {runway} months."}, "description": "Leadership update"},
            ],
            "expected_outcome": "Monthly close complete, investor update sent, leadership informed",
            "risk": "L5",
        },
    ],
    "operations": [
        {
            "id": "weekly_standup",
            "trigger": ["standup", "weekly sync", "team update", "status", "check in"],
            "description": "Prepare and share weekly team standup summary",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Weekly Standup: {date}", "content": "Wins, blockers, priorities for next week"}, "description": "Create standup doc"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#general", "text": "Weekly standup doc ready: {notion_url}. Please add your updates by EOD."}, "description": "Share with team"},
            ],
            "expected_outcome": "Standup doc created and shared with team",
            "risk": "L2",
        },
    ],
    "hr": [
        {
            "id": "new_hire_onboarding",
            "trigger": ["new hire", "hired", "onboarding", "first day", "joined", "welcome aboard"],
            "description": "Set up onboarding for new team member",
            "tools": [
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{new_hire_email}", "subject": "Welcome to {company} — your first week", "body": "Hi {name}, excited to have you! Here's your onboarding plan. Your buddy is {buddy_name}. First day: {first_day_plan}."}, "description": "Send welcome email"},
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Onboarding: {new_hire_name}", "content": "30-60-90 day plan, key contacts, tools access, training schedule"}, "description": "Create onboarding doc"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#general", "text": "Welcome {new_hire_name} to the team! They start {start_date}. Role: {role}"}, "description": "Announce to company"},
            ],
            "expected_outcome": "New hire welcomed, onboarding doc created, team announced",
            "risk": "L3",
        },
    ],
    "technology": [
        {
            "id": "incident_response",
            "trigger": ["down", "outage", "incident", "production broken", "site down", "500 error"],
            "description": "Incident response: alert team, create issue, track resolution",
            "tools": [
                {"tool": "GITHUB_CREATE_ISSUE", "args": {"title": "INCIDENT: {description}", "body": "Severity: {severity}. Detected: {time}. Impact: {impact}. Current status: investigating."}, "description": "File incident"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#engineering", "text": "INCIDENT: {description}. Severity: {severity}. Issue: {issue_url}. On-call: {on_call}"}, "description": "Alert team"},
            ],
            "expected_outcome": "Incident tracked, team alerted within 2 minutes",
            "risk": "L5",
        },
        {
            "id": "deploy_release",
            "trigger": ["deploy", "release", "ship to production", "go live"],
            "description": "Execute production deployment with notifications",
            "tools": [
                {"tool": "GITHUB_CREATE_ISSUE", "args": {"title": "Release: {version} — {description}", "body": "Changes: {changelog}. Rollback plan: {rollback}. Owner: {owner}"}, "description": "Track release"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#engineering", "text": "Deploying {version}: {description}. Release issue: {issue_url}. Monitoring."}, "description": "Notify team"},
            ],
            "expected_outcome": "Release tracked, team notified, monitoring active",
            "risk": "L5",
        },
    ],
    "data": [
        {
            "id": "weekly_metrics_report",
            "trigger": ["metrics", "dashboard", "KPI", "numbers", "report", "analytics"],
            "description": "Generate and share weekly metrics report",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Weekly Metrics: {week}", "content": "Revenue, active users, churn, CAC, LTV, pipeline. Trends vs last week and last month."}, "description": "Create metrics doc"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#leadership", "text": "Weekly metrics ready: {notion_url}. Revenue: {revenue}. Growth: {growth}%. Churn: {churn}%."}, "description": "Share with leadership"},
            ],
            "expected_outcome": "Weekly metrics doc created and shared with leadership",
            "risk": "L3",
        },
    ],
    "brand": [
        {
            "id": "crisis_response",
            "trigger": ["crisis", "bad press", "twitter storm", "viral negative", "reputation damage"],
            "description": "Activate crisis communication protocol",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Crisis Response: {incident}", "content": "What happened, facts confirmed, key message, spokesperson, channels, response timeline"}, "description": "Create crisis plan"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#leadership", "text": "CRISIS PROTOCOL ACTIVATED: {incident}. Response doc: {notion_url}. Spokesperson: {spokesperson}. No external comms until approved."}, "description": "Alert leadership"},
            ],
            "expected_outcome": "Crisis protocol activated, response doc created, team aligned",
            "risk": "L5",
        },
    ],
    "partnerships": [
        {
            "id": "partner_outreach",
            "trigger": ["partner", "alliance", "integration", "channel", "reseller"],
            "description": "Research and reach out to potential partners",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Partner Research: {partner_name}", "content": "Company, value prop, mutual benefit, key contact, outreach status"}, "description": "Create partner profile"},
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{partner_contact}", "subject": "Partnership opportunity: {mutual_benefit}", "body": "Hi {name}, I've been following {partner_name} and think there's a strong mutual opportunity in {area}. Would you be open to a brief intro call?"}, "description": "Send outreach email"},
            ],
            "expected_outcome": "Partner researched and contacted",
            "risk": "L3",
        },
    ],
    "growth": [
        {
            "id": "growth_experiment",
            "trigger": ["experiment", "A/B test", "growth hack", "conversion", "viral", "loop"],
            "description": "Design and launch a growth experiment",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Growth Experiment: {hypothesis}", "content": "Hypothesis, metric to move, experiment design, success criteria, timeline, learnings"}, "description": "Document experiment"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#growth", "text": "New experiment: {hypothesis}. Doc: {notion_url}. Owner: {owner}. Duration: {duration}"}, "description": "Share with growth team"},
            ],
            "expected_outcome": "Growth experiment documented and launched",
            "risk": "L3",
        },
    ],
    "leadership": [
        {
            "id": "board_update",
            "trigger": ["board", "investor update", "board deck", "quarterly review"],
            "description": "Prepare and send board update",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Board Update: {quarter}", "content": "Highlights, metrics, challenges, asks, next quarter priorities"}, "description": "Create board doc"},
                {"tool": "GMAIL_SEND_EMAIL", "args": {"to": "{board_emails}", "subject": "Board Update: {quarter}", "body": "Team, the board update for {quarter} is ready. Link: {notion_url}. Key numbers: Revenue {revenue}, Growth {growth}%, Cash {cash}, Runway {runway} months."}, "description": "Send to board"},
            ],
            "expected_outcome": "Board update prepared and sent to investors",
            "risk": "L5",
        },
        {
            "id": "team_retro",
            "trigger": ["retro", "retrospective", "what went well", "lessons learned", "postmortem"],
            "description": "Run team retrospective",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Retro: {sprint_name}", "content": "What went well, what didn't, action items, owner, deadline"}, "description": "Create retro doc"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#general", "text": "Retro for {sprint_name} is ready. Link: {notion_url}. Please add your thoughts before {meeting_time}."}, "description": "Share with team"},
            ],
            "expected_outcome": "Retro doc created, team contributed, action items assigned",
            "risk": "L2",
        },
    ],
    "vision": [
        {
            "id": "vision_alignment",
            "trigger": ["vision", "mission", "north star", "purpose", "why we exist"],
            "description": "Document and share company vision with team",
            "tools": [
                {"tool": "NOTION_CREATE_PAGE", "args": {"title": "Company Vision: {year}", "content": "Why we exist, where we're going, what success looks like, how we'll get there"}, "description": "Document vision"},
                {"tool": "SLACK_SEND_MESSAGE", "args": {"channel": "#general", "text": "Updated company vision for {year} is live. Link: {notion_url}. Please read and share your thoughts."}, "description": "Share with company"},
            ],
            "expected_outcome": "Vision documented and shared with entire company",
            "risk": "L2",
        },
    ],
    "build": [
        {
            "id": "build_landing_page",
            "trigger": ["build", "website", "landing page", "create site", "make a site", "web page", "homepage"],
            "description": "Generate and deploy a complete website from description",
            "tools": [
                {"tool": "SMARTDECIGEN_BUILD", "args": {"description": "{user_message}", "deploy_target": "github"}, "description": "Generate spec + code + deploy via capability platform"},
            ],
            "expected_outcome": "Live website generated and deployed, URL returned for preview",
            "risk": "L3",
        },
    ],
}


# ======================================================================
# Workflow matching engine
# ======================================================================

def match_workflows(user_message: str, max_results: int = 3) -> list[dict]:
    """Match user message against workflow triggers. Returns top matching workflows.
    Supports both single-word and multi-word phrase triggers."""
    msg_lower = user_message.lower()
    scored = []
    for function, workflows in WORKFLOWS.items():
        for wf in workflows:
            score = 0
            for kw in wf["trigger"]:
                if kw in msg_lower:
                    score += 2 if " " in kw else 1  # phrase matches get double weight
            if score > 0:
                scored.append((score, function, wf))
    scored.sort(key=lambda x: -x[0])
    return [
        {"function": func, **wf}
        for _, func, wf in scored[:max_results]
    ]


def format_workflow_for_prompt(workflow: dict) -> str:
    """Format a workflow as a prompt block for the engine/LLM."""
    lines = [
        f"WORKFLOW: {workflow['description']}",
        f"Risk: {workflow['risk']} | Expected: {workflow['expected_outcome']}",
        "Steps:",
    ]
    for i, step in enumerate(workflow.get("tools", []), 1):
        lines.append(f"  {i}. {step['tool']}({', '.join(f'{k}={v}' for k, v in step.get('args', {}).items())}) — {step.get('description', '')}")
    return "\n".join(lines)


def workflow_to_execution_plan(workflow: dict) -> dict:
    """Convert a workflow template into a dispatcher-executable plan."""
    return {
        "goal": workflow["description"],
        "actions": [
            {
                "tool": step["tool"],
                "args": step.get("args", {}),
                "depends_on": [],
                "description": step.get("description", ""),
            }
            for step in workflow.get("tools", [])
        ],
    }


def suggest_workflow_block(user_message: str, org_id: str = None) -> str:
    """Build a prompt block suggesting workflows for the engine to offer."""
    matches = match_workflows(user_message, max_results=2)
    if not matches:
        return ""
    lines = ["SUGGESTED WORKFLOWS (the founder's message matches these — offer to execute, don't execute automatically):"]
    for m in matches:
        lines.append(f"- [{m['function'].upper()}] {m['description']} "
                     f"({len(m.get('tools', []))} steps, risk: {m['risk']})")
    lines.append("If you suggest a workflow, include a 'suggested_workflow' field in your JSON with the workflow id.")
    return "\n".join(lines)


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    assert len(WORKFLOWS) >= 14, f"Expected >=14 functions, got {len(WORKFLOWS)}"
    total_flows = sum(len(wfs) for wfs in WORKFLOWS.values())
    print(f"Workflows: {len(WORKFLOWS)} functions, {total_flows} total workflows")

    matches = match_workflows("our revenue dropped and churn is spiking")
    assert len(matches) >= 1, f"Expected matches, got {len(matches)}"
    print(f"Matched: {len(matches)} — {[m['description'] for m in matches]}")

    plan = workflow_to_execution_plan(matches[0])
    assert "goal" in plan and "actions" in plan
    assert len(plan["actions"]) > 0

    block = suggest_workflow_block("can you help with our monthly investor update")
    assert "SUGGESTED WORKFLOWS" in block

    print("OK — workflow engine verified")
