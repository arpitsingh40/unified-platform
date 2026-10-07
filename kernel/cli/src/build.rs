//! Build command - compile agent.yaml to WASM component

use anyhow::{Context, Result};
use clap::Args;
use console::style;
use indicatif::{ProgressBar, ProgressStyle};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tokio::fs;
use tokio::process::Command;

#[derive(Args, Debug)]
pub struct BuildCommand {
    #[arg(short, long, default_value = "agent.yaml")]
    spec: PathBuf,
    
    #[arg(short, long)]
    output: Option<PathBuf>,
    
    #[arg(long)]
    target: Option<String>,
    
    #[arg(long, default_value = "release")]
    profile: String,
    
    #[arg(long)]
    sign: bool,
    
    #[arg(long)]
    no_verify: bool,
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

#[derive(Debug, Serialize, Deserialize)]
pub struct InputSpec {
    pub name: String,
    #[serde(rename = "type")]
    pub type_: String,
    pub required: bool,
    pub description: String,
}

#[derive(Debug, Serialize, Deserialize)]
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

impl BuildCommand {
    pub async fn execute(&self, _config: &crate::RuntimeConfig) -> Result<()> {
        let spec_path = &self.spec;
        let output_path = self.output.clone().unwrap_or_else(|| PathBuf::from("target/wasm32-wasip1/release/agent.wasm"));
        
        println!("{} Building agent from {}", style("→").blue(), spec_path.display());
        
        // Load and validate spec
        let spec = self.load_spec(spec_path).await?;
        
        // Create progress bar
        let pb = ProgressBar::new(4);
        pb.set_style(ProgressStyle::default_bar()
            .template("{spinner:.green} [{bar:40.cyan/blue}] {pos}/{len} {msg}")
            .unwrap()
            .progress_chars("##-"));
        
        // Step 1: Validate spec
        pb.set_message("Validating specification...");
        self.validate_spec(&spec)?;
        pb.inc(1);
        
        // Step 2: Generate component metadata
        pb.set_message("Generating component metadata...");
        self.generate_metadata(&spec, &output_path).await?;
        pb.inc(1);
        
        // Step 3: Build Rust component
        pb.set_message("Compiling Rust to WASM...");
        self.build_component(&spec, &self.profile, &self.target).await?;
        pb.inc(1);
        
        // Step 4: Sign component (if requested)
        if self.sign {
            pb.set_message("Signing component...");
            self.sign_component(&output_path).await?;
            pb.inc(1);
        } else {
            pb.inc(1);
        }
        
        pb.finish_with_message("Build complete!");
        
        println!("\n{} Agent built successfully!", style("✓").green());
        println!("  Component: {}", output_path.display());
        println!("  Spec:      {}", spec.name);
        println!("  Version:   {}", spec.version);
        
        Ok(())
    }
    
    async fn load_spec(&self, path: &PathBuf) -> Result<AgentSpec> {
        let content = fs::read_to_string(path).await?;
        let spec: AgentSpec = serde_yaml::from_str(&content)?;
        Ok(spec)
    }
    
    fn validate_spec(&self, spec: &AgentSpec) -> Result<()> {
        // Validate required fields
        if spec.name.is_empty() {
            return Err(anyhow::anyhow!("Agent name is required"));
        }
        if spec.version.is_empty() {
            return Err(anyhow::anyhow!("Agent version is required"));
        }
        if spec.capabilities.is_empty() {
            return Err(anyhow::anyhow!("At least one capability is required"));
        }
        
        // Validate authority level
        let valid_authorities = ["L1", "L2", "L3", "L4", "L5"];
        if !valid_authorities.contains(&spec.authority.as_str()) {
            return Err(anyhow::anyhow!("Invalid authority level: {}", spec.authority));
        }
        
        // Validate governance
        if spec.governance.max_tool_calls == 0 {
            return Err(anyhow::anyhow!("max_tool_calls must be > 0"));
        }
        if spec.governance.max_cost_usd <= 0.0 {
            return Err(anyhow::anyhow!("max_cost_usd must be > 0"));
        }
        
        Ok(())
    }
    
    async fn generate_metadata(&self, spec: &AgentSpec, output_path: &PathBuf) -> Result<()> {
        // Create component metadata
        let metadata = serde_json::json!({
            "name": spec.name,
            "version": spec.version,
            "description": spec.description,
            "author": spec.author,
            "spec_version": spec.spec_version,
            "capabilities": spec.capabilities,
            "authority": spec.authority,
            "schedule": spec.schedule,
            "governance": spec.governance,
            "memory": spec.memory,
            "built_at": chrono::Utc::now().to_rfc3339(),
        });
        
        let meta_path = output_path.with_extension("json");
        fs::write(&meta_path, serde_json::to_string_pretty(&metadata)?).await?;
        
        Ok(())
    }
    
    async fn build_component(&self, spec: &AgentSpec, profile: &str, target: &Option<String>) -> Result<()> {
        // Check if we're in a Rust project
        let cargo_toml = PathBuf::from("Cargo.toml");
        if !cargo_toml.exists() {
            return Err(anyhow::anyhow!("No Cargo.toml found. Run 'ari init' first or specify a Rust project."));
        }
        
        // Build with cargo
        let mut cmd = Command::new("cargo");
        cmd.arg("build");
        cmd.arg("--target").arg(target.as_deref().unwrap_or("wasm32-wasip1"));
        cmd.arg("--profile").arg(profile);
        cmd.arg("--lib");
        
        let output = cmd.output().await?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow::anyhow!("Build failed:\n{}", stderr));
        }
        
        // The WASM component will be at target/wasm32-wasip1/release/agent.wasm
        // For component model, we need to use cargo-component
        // This is a simplified version - real implementation would use wit-bindgen
        
        Ok(())
    }
    
    async fn sign_component(&self, path: &PathBuf) -> Result<()> {
        // In production, this would sign with the agent's private key
        // For now, just create a placeholder signature file
        let sig_path = path.with_extension("wasm.sig");
        fs::write(&sig_path, "SIGNATURE_PLACEHOLDER").await?;
        Ok(())
    }
}