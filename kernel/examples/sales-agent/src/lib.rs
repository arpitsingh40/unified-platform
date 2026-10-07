//! sales-agent — L3 pipeline health.
//! Input `context` expected shape (injected by host at `invoke`):
//! {
//!   "pipeline": [ { "id","name","stage","amount","owner","last_activity_at","next_step" } ],
//!   "account_health": { "acct_id": 0.7 },
//!   "pending_proposals": [ { "deal_id","sent_at" } ]
//! }
//! Export: `run` (JSON in, JSON out). When built as WASI cdylib, the host calls this via Component Model.
//! Also usable natively via `cargo test` / example binary.

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct PipelineDeal {
    pub id: String,
    #[serde(default)] pub name: String,
    #[serde(default)] pub stage: String,
    #[serde(default)] pub amount: f64,
    #[serde(default)] pub owner: String,
    #[serde(default)] pub last_activity_at: Option<String>,
    #[serde(default)] pub next_step: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ToolCall {
    pub capability: String,
    pub tool: String,
    pub args: serde_json::Value,
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct Decision {
    pub action: String,
    pub reasoning: String,
    pub tool_calls: Vec<ToolCall>,
    pub confidence: f64,
    pub review_after_days: u32,
}

/// Pure decision function — no I/O, no host calls. Testable offline.
pub fn decide(context: &serde_json::Value) -> Decision {
    let deals: Vec<PipelineDeal> = context.get("pipeline")
        .and_then(|v| serde_json::from_value(v.clone()).ok())
        .unwrap_or_default();

    let stalled: Vec<&PipelineDeal> = deals.iter()
        .filter(|d| is_stalled(d, 14))
        .collect();

    if stalled.is_empty() {
        return Decision {
            action: "NOTHING".to_string(),
            reasoning: format!("{} deals scanned, none stalled >14d. No action required.", deals.len()),
            tool_calls: vec![],
            confidence: 0.92,
            review_after_days: 1,
        };
    }

    // Highest leverage: stalled deal with highest amount.
    let target = stalled.iter().max_by(|a,b| a.amount.partial_cmp(&b.amount).unwrap()).unwrap();

    // L3 reversible: fetch enrichment + draft follow-up email (requires approval → queued as proposal).
    // We emit two tool_calls: crm.read enrichment (auto) + email.send (approval-gated).
    // Host will gate `email.send` per agent.yaml governance.requires_approval.
    let deal_id = target.id.clone();
    Decision {
        action: "FOLLOW_UP".to_string(),
        reasoning: format!("{} stalled deals detected (>14d). Highest value: {} (${:.0}) — drafting follow-up.", stalled.len(), target.name, target.amount),
        tool_calls: vec![
            ToolCall {
                capability: "crm.read".to_string(),
                tool: "crm.query".to_string(),
                args: serde_json::json!({"object":"Opportunity","id": deal_id, "include": ["contacts","activities"]}),
                reason: format!("Enrich stalled deal {}", deal_id),
            },
            ToolCall {
                capability: "email.send".to_string(),
                tool: "email.send".to_string(),
                args: serde_json::json!({
                    "deal_id": deal_id,
                    "template": "follow_up_stalled_14d",
                    "subject": format!("Re: {}", target.name),
                    "variables": { "deal_name": target.name, "owner": target.owner }
                }),
                reason: format!("Follow-up for stalled deal {} (approval required)", deal_id),
            },
        ],
        confidence: 0.84,
        review_after_days: 2,
    }
}

fn is_stalled(d: &PipelineDeal, days: i64) -> bool {
    // Parse last_activity_at as RFC3339; if missing or unparseable, treat as stalled if stage is not Closed.
    let is_closed = matches!(d.stage.to_lowercase().as_str(), "closed won" | "closed_won" | "closed lost" | "closed_lost");
    if is_closed { return false; }
    let Some(ts) = d.last_activity_at.as_deref() else { return true };
    let parsed = chrono::DateTime::parse_from_rfc3339(ts).ok().map(|dt| dt.with_timezone(&chrono::Utc));
    match parsed {
        Some(dt) => (chrono::Utc::now() - dt).num_days() > days,
        None => true,
    }
}

// WASI export surface — host will call this. Keep stable.
#[no_mangle]
pub extern "C" fn run(input_ptr: *const u8, input_len: usize, out_ptr: *mut u8, out_len: usize) -> i32 {
    // This is a stub for component builds; real component exports use wit-bindgen generate! instead.
    // Returning 0 signals success to the host's stub linker.
    let _ = (input_ptr, input_len, out_ptr, out_len);
    0
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn decides_nothing_when_empty() {
        let ctx = serde_json::json!({"pipeline": []});
        let d = decide(&ctx);
        assert_eq!(d.action, "NOTHING");
    }
    #[test]
    fn detects_stalled() {
        let old = (chrono::Utc::now() - chrono::Duration::days(20)).to_rfc3339();
        let ctx = serde_json::json!({"pipeline": [
            {"id":"opp_1","name":"Acme — Expansion","stage":"Negotiation","amount": 45000, "last_activity_at": old}
        ]});
        let d = decide(&ctx);
        assert_eq!(d.action, "FOLLOW_UP");
        assert_eq!(d.tool_calls.len(), 2);
    }
}
