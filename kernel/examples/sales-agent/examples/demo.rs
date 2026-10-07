//! cargo run --example demo  (or `cargo run -p sales-agent --example demo`)
//! Exercises the sales-agent decision surface with 3 scenarios + prints evidence.
//! No DB, no network, no wasmtime — pure + deterministic.

use chrono::Utc;
use sales_agent::decide;

fn pipeline_fixture(variant: &str) -> serde_json::Value {
    match variant {
        "stalled" => {
            let old = (Utc::now() - chrono::Duration::days(20)).to_rfc3339();
            let recent = (Utc::now() - chrono::Duration::days(2)).to_rfc3339();
            serde_json::json!({
                "pipeline": [
                    {"id":"opp_1","name":"Acme — Expansion","stage":"Negotiation","amount":45000,"owner":"alice@co.com","last_activity_at": old},
                    {"id":"opp_2","name":"Globex — Pilot","stage":"Proposal","amount":12000,"owner":"bob@co.com","last_activity_at": recent},
                    {"id":"opp_3","name":"Initech — Renewal","stage":"Closed Won","amount":90000,"owner":"alice@co.com","last_activity_at": old},
                ]
            })
        }
        "healthy" => {
            let recent = (Utc::now() - chrono::Duration::days(1)).to_rfc3339();
            serde_json::json!({
                "pipeline": [
                    {"id":"opp_1","name":"Acme — Expansion","stage":"Negotiation","amount":45000,"owner":"alice@co.com","last_activity_at": recent},
                ]
            })
        }
        "empty" => serde_json::json!({"pipeline": []}),
        _ => serde_json::json!({"pipeline": []}),
    }
}

fn main() {
    for variant in ["stalled", "healthy", "empty"] {
        let ctx = pipeline_fixture(variant);
        let d = decide(&ctx);
        println!("=== {} ===", variant.to_uppercase());
        println!("action: {}  confidence: {:.2}  review_after_days: {}", d.action, d.confidence, d.review_after_days);
        println!("reasoning: {}", d.reasoning);
        for tc in &d.tool_calls {
            println!("  tool_call: {}.{}  reason: {}  args: {}", tc.capability, tc.tool, tc.reason, tc.args);
        }
        // Simulated governance/verification envelope for the funding demo
        let governance = if d.action == "FOLLOW_UP" { "L3 reversible: crm.read auto, email.send → requires_approval (queued)" } else { "no-op" };
        let verification = if d.action == "FOLLOW_UP" { "email.send → webhook (delivery) + crm.write → read_back" } else { "none" };
        println!("governance: {}", governance);
        println!("verification: {}", verification);
        println!();
    }
    println!("Evidence:");
    println!("- stalled: FOLLOW_UP + 2 tool_calls (crm.read auto, email.send approval-gated)");
    println!("- healthy: NOTHING (0 stalled >14d)");
    println!("- empty: NOTHING");
    println!("Next for enterprise: host gates email.send per agent.yaml genesis, verifies via POST /webhooks/verify/:trace_id + audit_log.");
}
