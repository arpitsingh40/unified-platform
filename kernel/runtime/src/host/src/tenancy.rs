//! Tenant isolation — every request is org-scoped, no cross-tenant access.
//! Mirrors SmartDecigen's constitution: "org_id on every document".

use anyhow::{Context, Result};

/// Validate that the authenticated user's org_id matches the resource's org_id.
/// Call this at the top of every handler that takes an org_id param or body field.
pub fn assert_tenant(auth_org: &str, resource_org: &str) -> Result<()> {
    if auth_org != resource_org {
        anyhow::bail!("tenant isolation: auth org '{}' cannot access resource org '{}'", auth_org, resource_org);
    }
    Ok(())
}

/// Validate a CapabilityRequest is scoped to the caller's org.
/// Prevents an agent in org A from reading org B's CRM via capability registry.
pub fn assert_capability_tenant(auth_org: &str, request_org: &str, capability_id: &str) -> Result<()> {
    assert_tenant(auth_org, request_org).context(format!("capability '{}' tenant check failed", capability_id))
}

/// Memory key prefix check — agent memory keys are implicitly scoped by agent_id + org.
/// This is a defense-in-depth string check; primary isolation is via DB WHERE org_id.
pub fn memory_key_allowed(auth_org: &str, agent_org: &str) -> bool {
    auth_org == agent_org
}

/// Secrets: same check
pub fn secrets_tenant_ok(auth_org: &str, target_org: &str) -> bool {
    auth_org == target_org
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn tenant_ok() { assert!(assert_tenant("org_123", "org_123").is_ok()); }
    #[test]
    fn tenant_reject() { assert!(assert_tenant("org_123", "org_999").is_err()); }
}
