"""
Capability Registry — maps business capabilities to tool actions.

Replaces the hardcoded DEPARTMENT_TOOL_SCOPE dict.
find("Customer Communication") → [GMAIL_SEND_EMAIL, OUTLOOK_SEND_EMAIL, ...]

Built from the composio_catalog.json taxonomy (112 categories, 14 sections).
"""

import json
import logging
from pathlib import Path
from collections import defaultdict

log = logging.getLogger("execution.registry")

ROOT = Path(__file__).parent.parent.parent
CATALOG_PATH = ROOT / "memory" / "composio_catalog.json"

# ── Capability labels mapped to toolkit + action patterns ──
# These are derived from the taxonomy: category → capability → tool patterns
CAPABILITY_MAP: dict[str, list[dict]] = {}
_toolkit_index: dict[str, dict] = {}  # slug → toolkit info
_initialized = False


def _load_catalog():
    """Load composio catalog and build capability → tool mappings."""
    global CAPABILITY_MAP, _toolkit_index, _initialized
    if _initialized:
        return

    if not CATALOG_PATH.exists():
        log.warning(f"Catalog not found at {CATALOG_PATH}")
        _initialized = True
        return

    with open(CATALOG_PATH) as f:
        cat = json.load(f)

    toolkits = cat.get("toolkits", {})
    _toolkit_index = {slug.lower(): tk for slug, tk in toolkits.items() if tk.get("tools")}

    # Build capability → [tool_slugs] from category taxonomy
    for slug, tk in toolkits.items():
        category = tk.get("category", "")
        section = tk.get("section", "")
        category_why = tk.get("category_why", "")

        # Derive capabilities from category + tool descriptions
        capabilities = _derive_capabilities(tk, category, section)
        for cap in capabilities:
            if cap not in CAPABILITY_MAP:
                CAPABILITY_MAP[cap] = []
            for tool in tk.get("tools", []):
                CAPABILITY_MAP[cap].append({
                    "tool_slug": tool["slug"],
                    "tool_name": tool["name"],
                    "tool_desc": tool.get("desc", ""),
                    "toolkit": slug,
                    "toolkit_name": tk.get("name", slug),
                })

    _initialized = True
    log.info(f"Capability Registry loaded: {len(CAPABILITY_MAP)} capabilities, {len(_toolkit_index)} toolkits")


def _derive_capabilities(tk: dict, category: str, section: str) -> list[str]:
    """Derive capability labels from taxonomy categories (not tool keywords).
    Only uses the taxonomy section + category — tool-level keywords create false positives."""
    caps = set()

    # 1. From taxonomy section (broad domain)
    section_map = {
        "Sales & Revenue": ["customer_relationship", "lead_generation", "sales_outreach", "deal_management", "contract_management"],
        "Marketing & Growth": ["email_marketing", "social_media_management", "content_marketing", "digital_advertising", "seo", "marketing_automation"],
        "Customer Success & Support": ["customer_support", "live_chat", "feedback_collection", "customer_onboarding", "knowledge_base"],
        "Product & Engineering": ["code_review", "ci_cd", "infrastructure", "monitoring", "database", "authentication", "error_tracking", "web_scraping", "developer_tools"],
        "Data & Analytics": ["business_intelligence", "product_analytics", "data_warehousing", "etl", "data_enrichment", "data_visualization", "large_language_models"],
        "Finance & Operations": ["payment_processing", "invoicing", "accounting", "expense_management", "subscription_management", "crypto", "banking"],
        "People & HR": ["recruiting", "employee_management", "performance_review", "time_tracking", "learning_development", "payroll"],
        "Security & Compliance": ["identity_management", "security_monitoring", "compliance", "fraud_detection", "password_management"],
        "Design & Creative": ["graphic_design", "video_production", "image_editing", "audio_production", "ui_ux_design", "animation"],
        "Communication & Collaboration": ["email", "team_chat", "sms_voice", "push_notifications", "video_conferencing", "file_sharing", "calendar", "notes_docs", "forms_surveys", "project_management"],
        "E-commerce & Retail": ["ecommerce", "order_management", "marketplace", "pos"],
        "Education & Training": ["online_courses", "academic_research"],
        "Industry-Specific": ["healthcare", "real_estate", "travel", "logistics", "legal", "government", "energy", "agriculture", "manufacturing", "sports_gaming"],
        "Business Operations": ["workflow_automation", "document_generation", "geolocation", "weather", "news_media", "translation", "e_signatures", "qr_codes", "url_shortening"],
    }
    for s, caps_list in section_map.items():
        if s in section or section == s:
            caps.update(caps_list)

    # 2. From specific category name (more precise than section)
    cat_lower = category.lower()
    cat_cap_map = {
        "crm & customer relationships": ["customer_relationship"],
        "lead generation & prospecting": ["lead_generation"],
        "sales outreach & engagement": ["sales_outreach"],
        "deal pipeline & forecasting": ["deal_management"],
        "quotes, proposals & contracts": ["contract_management"],
        "email marketing & campaigns": ["email_marketing", "email"],
        "marketing automation": ["marketing_automation"],
        "social media management": ["social_media_management"],
        "seo & search marketing": ["seo"],
        "content marketing": ["content_marketing"],
        "digital advertising": ["digital_advertising"],
        "help desk & ticketing": ["customer_support"],
        "live chat & conversational support": ["live_chat"],
        "knowledge base & self-service": ["knowledge_base"],
        "customer feedback & nps": ["feedback_collection"],
        "version control & code repositories": ["code_review"],
        "ci/cd & build automation": ["ci_cd"],
        "infrastructure & cloud platforms": ["infrastructure"],
        "monitoring & observability": ["monitoring"],
        "database & storage": ["database"],
        "authentication & identity": ["authentication"],
        "error tracking & debugging": ["error_tracking"],
        "web scraping & browser automation": ["web_scraping"],
        "business intelligence & dashboards": ["business_intelligence"],
        "product & user analytics": ["product_analytics"],
        "data warehousing & lakes": ["data_warehousing"],
        "etl & data integration": ["etl"],
        "payment processing & gateways": ["payment_processing"],
        "invoicing & billing": ["invoicing"],
        "accounting & bookkeeping": ["accounting"],
        "expense management": ["expense_management"],
        "subscription & recurring billing": ["subscription_management"],
        "crypto, blockchain & web3": ["crypto"],
        "banking & treasury": ["banking"],
        "applicant tracking & recruiting": ["recruiting"],
        "hris & employee records": ["employee_management"],
        "time, attendance & scheduling": ["time_tracking"],
        "learning & development": ["learning_development"],
        "identity & access management (iam)": ["identity_management"],
        "security monitoring & threat detection": ["security_monitoring"],
        "compliance & audit": ["compliance"],
        "fraud detection & prevention": ["fraud_detection"],
        "graphic design & illustration": ["graphic_design"],
        "image & photo editing": ["image_editing"],
        "video production & editing": ["video_production"],
        "audio & podcast production": ["audio_production"],
        "ui/ux & prototyping": ["ui_ux_design"],
        "email service & transactional email": ["email"],
        "team chat & messaging": ["team_chat"],
        "sms, voice & telephony": ["sms_voice"],
        "push notifications": ["push_notifications"],
        "video conferencing & webinars": ["video_conferencing"],
        "file sharing & document collaboration": ["file_sharing"],
        "calendar & scheduling": ["calendar"],
        "notes, docs & wikis": ["notes_docs"],
        "forms, surveys & data collection": ["forms_surveys"],
        "project management & workflow": ["project_management"],
        "e-commerce platforms & storefronts": ["ecommerce"],
        "order management & fulfillment": ["order_management"],
        "workflow automation & ipaas": ["workflow_automation"],
        "document generation & management": ["document_generation"],
        "geolocation & mapping": ["geolocation"],
        "weather & environmental data": ["weather"],
        "translation & localization": ["translation"],
        "e-signatures & digital agreements": ["e_signatures"],
        "qr codes & barcodes": ["qr_codes"],
        "url shortening & link management": ["url_shortening"],
        "point of sale (pos)": ["pos"],
        "online courses & lms": ["online_courses"],
    }
    for cat_key, cap_names in cat_cap_map.items():
        if cat_key in cat_lower:
            caps.update(cap_names)

    if not caps:
        caps.add("general")

    return list(caps)


def find(capability: str, limit: int = 20) -> list[dict]:
    """Find tool actions for a business capability.
    Example: find("customer_communication") → [GMAIL_SEND_EMAIL, OUTLOOK_SEND_EMAIL, ...]
    Supports fuzzy matching against capability names and synonyms.
    """
    _load_catalog()

    cap_lower = capability.lower().replace(" ", "_").replace("-", "_")

    # Synonym map
    synonyms = {
        "send_email": "email",
        "communicate": "email",
        "customer_communication": "email",
        "customer_outreach": "email",
        "customer_email": "email",
        "cold_outreach": "email",
        "schedule_meeting": "calendar",
        "book_meeting": "calendar",
        "create_task": "project_management",
        "assign_task": "project_management",
        "send_sms": "sms_voice",
        "text_message": "sms_voice",
        "make_call": "sms_voice",
        "review_code": "code_review",
        "merge_pr": "code_review",
        "deploy_app": "ci_cd",
        "run_pipeline": "ci_cd",
        "process_payment": "payment_processing",
        "charge_customer": "payment_processing",
        "send_invoice": "invoicing",
        "generate_report": "business_intelligence",
        "analyze_data": "business_intelligence",
        "post_social": "social_media_management",
        "hire_candidate": "recruiting",
        "search_web": "web_scraping",
        "extract_data": "web_scraping",
        "send_notification": "push_notifications",
        "manage_files": "file_sharing",
        "upload_file": "file_sharing",
        "generate_document": "document_generation",
        "create_pdf": "document_generation",
        "translate_text": "translation",
        "get_weather": "weather",
        "find_location": "geolocation",
        "get_directions": "geolocation",
        "manage_contacts": "customer_relationship",
        "find_leads": "lead_generation",
        "run_ad": "digital_advertising",
        "optimize_seo": "seo",
        "create_design": "graphic_design",
        "edit_image": "image_editing",
        "produce_video": "video_production",
        "record_audio": "audio_production",
        "monitor_system": "monitoring",
        "check_status": "monitoring",
        "auth_user": "authentication",
        "login_user": "authentication",
        "encrypt_data": "identity_management",
        "track_time": "time_tracking",
        "log_hours": "time_tracking",
        "create_course": "online_courses",
        "manage_inventory": "ecommerce",
        "process_order": "order_management",
        "automate_workflow": "workflow_automation",
        "sign_document": "e_signatures",
        "scan_qr": "qr_codes",
        "shorten_url": "url_shortening",
    }

    resolved = synonyms.get(cap_lower, cap_lower)

    # Direct match
    if resolved in CAPABILITY_MAP:
        return CAPABILITY_MAP[resolved][:limit]

    # Fuzzy match — check if capability name is a substring
    for cap_name, tools in CAPABILITY_MAP.items():
        if resolved in cap_name or cap_name in resolved:
            return tools[:limit]

    # Fallback: search across all tools whose names/descs contain keywords
    keyword = resolved.replace("_", " ")
    results = []
    for cap_name, tools in CAPABILITY_MAP.items():
        for t in tools:
            text = f"{t['tool_slug']} {t['tool_name']} {t['tool_desc']}".lower()
            if keyword in text:
                results.append(t)
    return results[:limit]


def capabilities_for_department(function: str, limit: int = 30) -> list[dict]:
    """Get tools for a department based on capabilities relevant to that function."""
    dept_caps = {
        "sales": ["email", "customer_relationship", "lead_generation", "calendar", "payment_processing", "contract_management"],
        "marketing": ["email_marketing", "social_media_management", "content_marketing", "seo", "digital_advertising", "email"],
        "engineering": ["code_review", "ci_cd", "infrastructure", "monitoring", "database", "authentication", "error_tracking"],
        "product": ["project_management", "code_review", "notes_docs", "team_chat", "monitoring"],
        "operations": ["email", "project_management", "calendar", "file_sharing", "workflow_automation"],
        "finance": ["payment_processing", "invoicing", "accounting", "email", "subscription_management"],
        "leadership": [],
        "general": ["email", "calendar", "project_management", "notes_docs"],
    }

    caps = dept_caps.get(function, dept_caps["general"])
    results = []
    seen = set()
    for cap in caps:
        for tool in find(cap):
            if tool["tool_slug"] not in seen:
                results.append(tool)
                seen.add(tool["tool_slug"])
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break
    return results


# ── Demo ──
def _demo():
    _load_catalog()
    tests = {
        "send_email": find("send_email", 3),
        "calendar": find("book_meeting", 3),
        "payment": find("process_payment", 3),
        "code_review": find("review_code", 3),
        "marketing_sales": capabilities_for_department("sales", 5),
    }
    result = {}
    for name, tools in tests.items():
        result[name] = [t["tool_slug"] for t in tools] if tools else ["(no tools)"]
    result["total_capabilities"] = len(CAPABILITY_MAP)
    result["status"] = "OK"
    return result


if __name__ == "__main__":
    print(json.dumps(_demo(), indent=2, default=str))
