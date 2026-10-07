//! ARI Host Runtime - Main entry point
//!
//! This is the core host that runs WASM agent components with full
//! governance, capabilities, and verification.

use anyhow::Result;
use tracing::{info, warn};
use clap::{Parser, Subcommand};

use ari_runtime_host::{AriRuntime, RuntimeConfig};

#[derive(Parser)]
#[command(name = "ari-host")]
#[command(about = "ARI Host Runtime - WASM Agent Execution Engine")]
#[command(version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the host runtime server
    Serve {
        #[arg(short, long, default_value = "config.yaml")]
        config: String,
        
        #[arg(long, default_value = "8080")]
        port: u16,
    },
    
    /// Run a single agent invocation
    Run {
        #[arg(short, long)]
        agent_id: String,
        
        #[arg(short, long)]
        input: String,
        
        #[arg(short, long, default_value = "config.yaml")]
        config: String,
    },
    
    /// Validate agent component
    Validate {
        #[arg(short, long)]
        component: String,
    },
    
    /// Generate agent identity
    GenIdentity {
        #[arg(short, long)]
        agent_id: String,
        
        #[arg(short, long)]
        org_id: String,
        
        #[arg(short, long, default_value = "config.yaml")]
        config: String,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    
    // Initialize telemetry first
    ari_runtime_host::telemetry::init_telemetry()?;
    
    match cli.command {
        Commands::Serve { config, port } => {
            info!("Starting ARI Host Runtime on port {}", port);
            
            let config = RuntimeConfig::load(&config)?;
            
            let runtime = AriRuntime::new(config).await?;
            runtime.start().await?;
            
            info!("Runtime started successfully");
            
            // Keep running
            tokio::signal::ctrl_c().await?;
            info!("Shutting down...");
            runtime.shutdown().await?;
        }
        Commands::Run { agent_id, input, config } => {
            info!("Running agent: {}", agent_id);
            
            let config = RuntimeConfig::load(&config)?;
            let runtime = AriRuntime::new(config).await?;
            
            let request = ari_runtime_host::InvocationRequest {
                invocation_id: uuid::Uuid::new_v4().to_string(),
                agent_id: agent_id.clone(),
                org_id: "default".to_string(), // Would come from config
                context: serde_json::from_str(&input)?,
                trace_parent: None,
            };
            
            let result = runtime.runtime.invoke(request).await?;
            println!("{}", serde_json::to_string_pretty(&result)?);
            
            runtime.shutdown().await?;
        }
        Commands::Validate { component } => {
            info!("Validating component: {}", component);
            // TODO: Implement validation
        }
        Commands::GenIdentity { agent_id, org_id, config } => {
            info!("Generating identity for agent: {} (org: {})", agent_id, org_id);
            
            let config = RuntimeConfig::load(&config)?;
            let runtime = AriRuntime::new(config).await?;
            
            let identity = runtime.identity.create_agent_identity(
                &agent_id,
                &org_id,
                vec![],
                "L1",
            ).await?;
            
            println!("{}", serde_json::to_string_pretty(&identity)?);
            
            runtime.shutdown().await?;
        }
    }
    
    Ok(())
}