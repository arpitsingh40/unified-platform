//! Spec command - validate agent specification

use anyhow::{Context, Result};
use clap::Args;
use console::style;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tokio::fs;

#[derive(Args, Debug)]
pub struct SpecCommand {
    #[arg(short, long, default_value = "agent.yaml")]
    file: PathBuf,
    
    #[arg(long)]
    strict: bool,
    
    #[arg(long)]
    output: Option<PathBuf>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AgentSpec {
    pub name: String,
    pub version: String,
    pub description: String,
    pub author: String,
    pub spec_version: String,
    pub capabilities: Vec<String>,
    pub authority: String,
    pub schedule: String,
    pub inputs: Vec<InputSpec>,
    pub outputs: Vec<OutputSpec>,
    pub governance: GovernanceSpec,
    pub memory: MemorySpec,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InputSpec {
    pub name: String,
    #[serde(rename = "type")]
    pub type_: String,
    pub required: bool,
    pub description: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputSpec {
    pub name: String,
    #[serde(rename = "type")]
    pub type_: String,
    pub description: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GovernanceSpec {
    pub max_tool_calls: u32,
    pub max_cost_usd: f64,
    pub max_execution_time_ms: u64,
    pub requires_approval_above_usd: f64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MemorySpec {
    pub backend: String,
    pub ttl_days: u32,
}

impl SpecCommand {
    pub async fn execute(&self, _config: &crate::RuntimeConfig) -> Result<()> {
        let spec_path = &self.file;
        
        println!("{} Validating specification: {}", style("â†’").blue(), spec_path.display());
        
        let content = fs::read_to_string(spec_path).await?;
        let spec: AgentSpec = serde_yaml::from_str(&content)?;
        
        let mut errors = Vec::new();
        let mut warnings = Vec::new();
        
        // Run validations
        self.validate_required_fields(&spec, &mut errors);
        self.validate_version(&spec, &mut errors, &mut warnings);
        self.validate_capabilities(&spec, &mut errors, &mut warnings);
        self.validate_authority(&spec, &mut errors);
        self.validate_schedule(&spec, &mut warnings);
        self.validate_inputs_outputs(&spec, &mut errors, &mut warnings);
        self.validate_governance(&spec, &mut errors, &mut warnings);
        self.validate_memory(&spec, &mut warnings);
        
        // Output results
        if !errors.is_empty() {
            println!("\n{} Validation failed with {} error(s):", style("âœ—").red(), errors.len());
            for err in &errors {
                println!("  {} {}", style("âœ—").red(), err);
            }
        }
        
        if !warnings.is_empty() {
            println!("\n{} {} warning(s):", style("âš ").yellow(), warnings.len());
            for warn in &warnings {
                println!("  {} {}", style("âš ").yellow(), warn);
            }
        }
        
        if errors.is_empty() && warnings.is_empty() {
            println!("\n{} Specification is valid!", style("âœ“").green());
        } else if errors.is_empty() {
            println!("\n{} Specification is valid with warnings", style("âœ“").green());
        }
        
        // Write normalized spec if output requested
        if let Some(output_path) = &self.output {
            let normalized = self.normalize_spec(&spec)?;
            fs::write(output_path, serde_yaml::to_string(&normalized)?).await?;
            println!("\n{} Normalized spec written to: {}", style("â†’").blue(), output_path.display());
        }
        
        if !errors.is_empty() {
            return Err(anyhow::anyhow!("Specification validation failed"));
        }
        
        Ok(())
    }
    
    fn validate_required_fields(&self, spec: &AgentSpec, errors: &mut Vec<String>) {
        if spec.name.trim().is_empty() {
            errors.push("name is required".to_string());
        }
        if spec.version.trim().is_empty() {
            errors.push("version is required".to_string());
        }
        if spec.description.trim().is_empty() {
            errors.push("description is required".to_string());
        }
        if spec.author.trim().is_empty() {
            errors.push("author is required".to_string());
        }
        if spec.spec_version.trim().is_empty() {
            errors.push("spec_version is required".to_string());
        }
        if spec.capabilities.is_empty() {
            errors.push("at least one capability is required".to_string());
        }
        if spec.authority.trim().is_empty() {
            errors.push("authority is required".to_string());
        }
        if spec.schedule.trim().is_empty() {
            errors.push("schedule is required".to_string());
        }
    }
    
    fn validate_version(&self, spec: &AgentSpec, errors: &mut Vec<String>, warnings: &mut Vec<String>) {
        // Semver validation
        let parts: Vec<&str> = spec.version.split('.').collect();
        if parts.len() < 3 {
            warnings.push("version should follow semver (major.minor.patch)".to_string());
        }
        
        for part in parts {
            if part.parse::<u32>().is_err() && !part.contains('-') {
                warnings.push(format!("version part '{}' is not numeric", part));
            }
        }
    }
    
    fn validate_capabilities(&self, spec: &AgentSpec, errors: &mut Vec<String>, warnings: &mut Vec<String>) {
        let known_capabilities = ["http", "email", "crm", "slack", "github", "aws", "gcp", "azure"];
        
        for cap in &spec.capabilities {
            if !known_capabilities.contains(&cap.as_str()) {
                if self.strict {
                    errors.push(format!("unknown capability: {}", cap));
                } else {
                    warnings.push(format!("unknown capability (not in registry): {}", cap));
                }
            }
        }
        
        if spec.capabilities.len() > 20 {
            warnings.push("large number of capabilities may increase attack surface".to_string());
        }
    }
    
    fn validate_authority(&self, spec: &AgentSpec, errors: &mut Vec<String>) {
        let valid = ["L1", "L2", "L3", "L4", "L5"];
        if !valid.contains(&spec.authority.as_str()) {
            errors.push(format!("invalid authority level: {} (must be one of: {})", 
                spec.authority, valid.join(", ")));
        }
    }
    
    fn validate_schedule(&self, spec: &AgentSpec, warnings: &mut Vec<String>) {
        // Basic cron validation
        let parts: Vec<&str> = spec.schedule.split_whitespace().collect();
        if parts.len() != 5 && parts.len() != 6 {
            warnings.push("schedule should be a valid cron expression (5 or 6 fields)".to_string());
        }
        
        // Check for common patterns
        if spec.schedule == "* * * * *" {
            warnings.push("schedule runs every minute - consider if this is intentional".to_string());
        }
    }
    
    fn validate_inputs_outputs(&self, spec: &AgentSpec, errors: &mut Vec<String>, warnings: &mut Vec<String>) {
        let mut input_names = std::collections::HashSet::new();
        for input in &spec.inputs {
            if input.name.trim().is_empty() {
                errors.push("input name cannot be empty".to_string());
            }
            if !input_names.insert(&input.name) {
                errors.push(format!("duplicate input name: {}", input.name));
            }
            if input.type_.trim().is_empty() {
                errors.push(format!("input '{}' type is required", input.name));
            }
        }
        
        let mut output_names = std::collections::HashSet::new();
        for output in &spec.outputs {
            if output.name.trim().is_empty() {
                errors.push("output name cannot be empty".to_string());
            }
            if !output_names.insert(&output.name) {
                errors.push(format!("duplicate output name: {}", output.name));
            }
            if output.type_.trim().is_empty() {
                errors.push(format!("output '{}' type is required", output.name));
            }
        }
        
        // Check for decision output
        if !spec.outputs.iter().any(|o| o.name == "decision") {
            warnings.push("recommended to have a 'decision' output for agent results".to_string());
        }
    }
    
    fn validate_governance(&self, spec: &AgentSpec, errors: &mut Vec<String>, warnings: &mut Vec<String>) {
        if spec.governance.max_tool_calls == 0 {
            errors.push("max_tool_calls must be > 0".to_string());
        }
        if spec.governance.max_tool_calls > 100 {
            warnings.push("max_tool_calls > 100 may cause runaway executions".to_string());
        }
        
        if spec.governance.max_cost_usd <= 0.0 {
            errors.push("max_cost_usd must be > 0".to_string());
        }
        if spec.governance.max_cost_usd > 100.0 {
            warnings.push("max_cost_usd > $100 - ensure budget controls are in place".to_string());
        }
        
        if spec.governance.max_execution_time_ms == 0 {
            errors.push("max_execution_time_ms must be > 0".to_string());
        }
        if spec.governance.max_execution_time_ms > 3_600_000 {
            warnings.push("max_execution_time_ms > 1 hour - consider if this is intentional".to_string());
        }
        
        if spec.governance.requires_approval_above_usd < 0.0 {
            errors.push("requires_approval_above_usd cannot be negative".to_string());
        }
    }
    
    fn validate_memory(&self, spec: &AgentSpec, warnings: &mut Vec<String>) {
        let valid_backends = ["inmemory", "redis", "postgres"];
        if !valid_backends.contains(&spec.memory.backend.to_lowercase().as_str()) {
            warnings.push(format!("unknown memory backend: {} (valid: {})", 
                spec.memory.backend, valid_backends.join(", ")));
        }
        
        if spec.memory.ttl_days == 0 {
            warnings.push("memory ttl_days is 0 - data will never expire".to_string());
        }
        if spec.memory.ttl_days > 365 {
            warnings.push("memory ttl_days > 365 - consider storage costs".to_string());
        }
    }
    
    fn normalize_spec(&self, spec: &AgentSpec) -> Result<AgentSpec> {
        // Return a normalized version with defaults filled in
        Ok(AgentSpec {
            name: spec.name.trim().to_string(),
            version: spec.version.trim().to_string(),
            description: spec.description.trim().to_string(),
            author: spec.author.trim().to_string(),
            spec_version: spec.spec_version.trim().to_string(),
            capabilities: spec.capabilities.iter().map(|c| c.trim().to_string()).collect(),
            authority: spec.authority.trim().to_uppercase(),
            schedule: spec.schedule.trim().to_string(),
            inputs: spec.inputs.clone(),
            outputs: spec.outputs.clone(),
            governance: GovernanceSpec {
                max_tool_calls: spec.governance.max_tool_calls.max(1),
                max_cost_usd: spec.governance.max_cost_usd.max(0.01),
                max_execution_time_ms: spec.governance.max_execution_time_ms.max(1000),
                requires_approval_above_usd: spec.governance.requires_approval_above_usd.max(0.0),
            },
            memory: MemorySpec {
                backend: spec.memory.backend.to_lowercase(),
                ttl_days: spec.memory.ttl_days.max(1),
            },
        })
    }
}