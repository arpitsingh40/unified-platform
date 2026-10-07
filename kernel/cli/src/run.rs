//! Run command - execute agent locally

use anyhow::{Context, Result};
use clap::Args;
use console::style;
use indicatif::{ProgressBar, ProgressStyle};
use serde_json::json;
use std::path::PathBuf;
use tokio::fs;

use ari_runtime_host::{AriRuntime, RuntimeConfig, InvocationRequest};

#[derive(Args, Debug)]
pub struct RunCommand {
    #[arg(short, long, default_value = "agent.yaml")]
    spec: PathBuf,
    
    #[arg(short, long)]
    input: Option<String>,
    
    #[arg(short, long)]
    input_file: Option<PathBuf>,
    
    #[arg(long)]
    agent_id: Option<String>,
    
    #[arg(long)]
    dry_run: bool,
    
    #[arg(long)]
    verbose: bool,
}

impl RunCommand {
    pub async fn execute(&self, config: &RuntimeConfig) -> Result<()> {
        let spec_path = &self.spec;
        
        println!("{} Running agent locally", style("→").blue());
        
        // Load spec to get agent name
        let spec_content = fs::read_to_string(spec_path).await?;
        let spec: serde_json::Value = serde_yaml::from_str(&spec_content)?;
        let agent_name = spec["name"].as_str().unwrap_or("agent");
        let agent_id = self.agent_id.clone().unwrap_or_else(|| agent_name.to_string());
        
        // Prepare input
        let input = self.prepare_input().await?;
        
        // Create runtime
        let runtime = AriRuntime::new(config.clone()).await?;
        
        // Run invocation
        let request = InvocationRequest {
            invocation_id: uuid::Uuid::new_v4().to_string(),
            agent_id: agent_id.clone(),
            org_id: "local".to_string(),
            context: input,
            trace_parent: None,
        };
        
        let pb = ProgressBar::new_spinner();
        pb.set_style(ProgressStyle::default_spinner()
            .template("{spinner:.green} {msg}")
            .unwrap());
        pb.set_message("Executing agent...");
        
        let result = runtime.runtime.invoke(request).await?;
        
        pb.finish_and_clear();
        
        // Display result
        self.display_result(&result, self.verbose).await?;
        
        runtime.shutdown().await?;
        
        if !result.success {
            return Err(anyhow::anyhow!("Agent execution failed: {:?}", result.error));
        }
        
        Ok(())
    }
    
    async fn prepare_input(&self) -> Result<serde_json::Value> {
        if let Some(input_str) = &self.input {
            return Ok(serde_json::from_str(input_str)?);
        }
        
        if let Some(input_file) = &self.input_file {
            let content = fs::read_to_string(input_file).await?;
            return Ok(serde_json::from_str(&content)?);
        }
        
        // Default empty context
        Ok(json!({}))
    }
    
    async fn display_result(&self, result: &ari_runtime_host::InvocationResult, verbose: bool) -> Result<()> {
        println!("\n{} Execution complete", if result.success { style("✓").green() } else { style("✗").red() });
        println!("  Invocation ID: {}", result.invocation_id);
        println!("  Agent ID:      {}", result.agent_id);
        println!("  Duration:      {}ms", result.total_time_ms);
        println!("  Cost:          ${:.6}", result.total_cost_usd);
        
        if let Some(decision) = &result.decision {
            println!("\n{} Decision:", style("→").blue());
            println!("  Action:     {}", decision.action);
            println!("  Reasoning:  {}", decision.reasoning);
            println!("  Confidence: {:.0}%", decision.confidence * 100.0);
            println!("  Review in:  {} days", decision.review_after_days);
            
            if !decision.tool_calls.is_empty() {
                println!("\n  Tool Calls:");
                for (i, call) in decision.tool_calls.iter().enumerate() {
                    println!("    {}. {}::{}", i + 1, call.capability, call.tool);
                    if verbose {
                        println!("       Reason: {}", call.reason);
                        println!("       Args:   {}", serde_json::to_string_pretty(&call.args)?);
                    }
                }
            }
        }
        
        if !result.executions.is_empty() {
            println!("\n{} Executions:", style("→").blue());
            for (i, exec) in result.executions.iter().enumerate() {
                let status = if exec.error.is_none() { style("✓").green() } else { style("✗").red() };
                println!("  {}. {} {}::{} - {}ms - ${:.6}", 
                    i + 1, status, exec.capability, exec.tool, exec.execution_time_ms, exec.cost_usd);
                if let Some(err) = &exec.error {
                    println!("     Error: {}", err);
                }
                if verbose && exec.result.is_some() {
                    println!("     Result: {}", serde_json::to_string_pretty(&exec.result)?);
                }
            }
        }
        
        if !result.verification.is_empty() {
            println!("\n{} Verification:", style("→").blue());
            for v in &result.verification {
                let status = match v.outcome.as_str() {
                    "Success" => style("✓").green(),
                    "Partial" => style("~").yellow(),
                    _ => style("✗").red(),
                };
                println!("  {} {} - {:.0}% - {}", status, v.capability, v.confidence * 100.0, v.insight);
            }
        }
        
        if verbose {
            println!("\n{} Full Result:", style("→").blue());
            println!("{}", serde_json::to_string_pretty(result)?);
        }
        
        Ok(())
    }
}