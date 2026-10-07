//! ARI CLI - Build, deploy, and run agents

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use console::style;
use indicatif::{ProgressBar, ProgressStyle};
use std::path::PathBuf;
use tokio::fs;

use ari_runtime_host::{RuntimeConfig, AriRuntime};

mod build;
mod push;
mod deploy;
mod run;
mod spec;

use build::BuildCommand;
use push::PushCommand;
use deploy::DeployCommand;
use run::RunCommand;
use spec::SpecCommand;

#[derive(Parser)]
#[command(name = "ari")]
#[command(about = "ARI CLI - Build, deploy, and run agents on the Agent Runtime Infrastructure")]
#[command(version)]
#[command(long_about = r#"
ARI (Agent Runtime Infrastructure) CLI

A trillion-dollar platform for running autonomous agents with:
- WASM-based isolation
- Capability registry with governance
- Built-in verification & approval workflows
- Cryptographic identity & signing

Commands:
  ari build     Compile agent.yaml → signed WASM component
  ari push      Push component to registry
  ari deploy    Deploy to control plane
  ari run       Execute agent locally
  ari spec      Validate agent specification
"#)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
    
    #[arg(short, long, global = true)]
    config: Option<PathBuf>,
    
    #[arg(short, long, global = true)]
    verbose: bool,
}

#[derive(Subcommand)]
enum Commands {
    /// Compile agent.yaml to WASM component
    Build(BuildCommand),
    
    /// Push component to registry
    Push(PushCommand),
    
    /// Deploy agent to control plane
    Deploy(DeployCommand),
    
    /// Run agent locally
    Run(RunCommand),
    
    /// Validate agent specification
    Spec(SpecCommand),
    
    /// Initialize new agent project
    Init {
        #[arg(short, long)]
        name: String,
        
        #[arg(short, long, default_value = ".")]
        dir: PathBuf,
        
        #[arg(long)]
        template: Option<String>,
    },
    
    /// Generate agent identity
    GenIdentity {
        #[arg(short, long)]
        agent_id: String,
        
        #[arg(short, long)]
        org_id: String,
    },
    
    /// Validate WASM component
    Validate {
        #[arg(short, long)]
        component: PathBuf,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    // Initialize logging
    if cli.verbose {
        std::env::set_var("RUST_LOG", "debug");
    }
    tracing_subscriber::fmt::init();
    
    let config_path = cli.config.unwrap_or_else(|| PathBuf::from("config.yaml"));
    let config = RuntimeConfig::load(config_path.to_str().unwrap())?;
    
    let result = match cli.command {
        Commands::Build(cmd) => cmd.execute(&config).await,
        Commands::Push(cmd) => cmd.execute(&config).await,
        Commands::Deploy(cmd) => cmd.execute(&config).await,
        Commands::Run(cmd) => cmd.execute(&config).await,
        Commands::Spec(cmd) => cmd.execute(&config).await,
        Commands::Init { name, dir, template } => init_agent(name, dir, template).await,
        Commands::GenIdentity { agent_id, org_id } => gen_identity(&config, &agent_id, &org_id).await,
        Commands::Validate { component } => validate_component(component).await,
    };
    
    if let Err(e) = &result {
        eprintln!("{} {}", style("Error:").red().bold(), e);
    }
    
    result
}

async fn init_agent(name: String, dir: PathBuf, template: Option<String>) -> Result<()> {
    let agent_dir = dir.join(&name);
    fs::create_dir_all(&agent_dir).await?;
    
    let template = template.unwrap_or_else(|| "default".to_string());
    
    // Create agent.yaml
    let agent_yaml = format!(r#"
name: "{}"
version: "0.1.0"
description: "A new ARI agent"
author: "Your Name"

spec_version: "1.0"

capabilities:
  - http
  - email

authority: "L1"
schedule: "0 9 * * *"  # Daily at 9 AM

inputs:
  - name: "context"
    type: "object"
    required: true
    description: "Execution context"

outputs:
  - name: "decision"
    type: "object"
    description: "Agent decision with tool calls"

governance:
  max_tool_calls: 20
  max_cost_usd: 1.0
  max_execution_time_ms: 300000
  requires_approval_above_usd: 0.10

memory:
  backend: "postgres"
  ttl_days: 30
"#, name);
    
    fs::write(agent_dir.join("agent.yaml"), agent_yaml).await?;
    
    // Create src directory
    fs::create_dir_all(agent_dir.join("src")).await?;
    
    // Create a sample Rust component
    let cargo_toml = r#"
[package]
name = "agent"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib"]

[dependencies]
ari-guest = { path = "../../../runtime/src/guest" }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
anyhow = "1.0"
"#;
    
    fs::write(agent_dir.join("Cargo.toml"), cargo_toml).await?;
    
    let lib_rs = r#"
use ari_guest::{AgentInput, AgentResult, AgentDecision, ToolCall, run};
use serde_json::json;
use anyhow::Result;

#[no_mangle]
pub extern "C" fn run(input: AgentInput) -> AgentResult {
    // Your agent logic here
    let decision = AgentDecision {
        action: "ANALYZE".to_string(),
        reasoning: "Analyzing pipeline data".to_string(),
        tool_calls: vec![
            ToolCall {
                capability: "crm".to_string(),
                tool: "crm.query".to_string(),
                args: json!({
                    "object": "Opportunity",
                    "filter": { "stage": { "$ne": "Closed Won" } },
                    "limit": 50
                }),
                reason: "Get current pipeline".to_string(),
            }
        ],
        confidence: 0.85,
        review_after_days: 1,
    };
    
    AgentResult {
        success: true,
        decision: Some(decision),
        error: None,
    }
}
"#;
    
    fs::write(agent_dir.join("src").join("lib.rs"), lib_rs).await?;
    
    // Create README
    let readme = format!(r#"
# {} Agent

An ARI agent built for the Agent Runtime Infrastructure.

## Building

```bash
ari build
```

## Running locally

```bash
ari run
```

## Deploying

```bash
ari push
ari deploy
```
"#, name);
    
    fs::write(agent_dir.join("README.md"), readme).await?;
    
    println!("{} Created agent project: {}", style("✓").green(), style(&name).bold());
    println!("  Directory: {}", agent_dir.display());
    println!("  Template:  {}", template);
    
    Ok(())
}

async fn gen_identity(config: &RuntimeConfig, agent_id: &str, org_id: &str) -> Result<()> {
    let runtime = AriRuntime::new(config.clone()).await?;
    
    let identity = runtime.identity.create_agent_identity(
        agent_id,
        org_id,
        vec!["http".to_string(), "email".to_string()],
        "L1",
    ).await?;
    
    println!("{}", serde_json::to_string_pretty(&identity)?);
    
    runtime.shutdown().await?;
    Ok(())
}

async fn validate_component(path: PathBuf) -> Result<()> {
    println!("{} Validating component: {}", style("→").blue(), path.display());
    
    // TODO: Implement component validation
    // - Check component model compliance
    // - Verify required exports
    // - Validate signatures
    
    println!("{} Component validation not yet implemented", style("⚠").yellow());
    Ok(())
}