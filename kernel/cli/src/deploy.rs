//! Deploy command - deploy agent to control plane

use anyhow::{Context, Result};
use clap::Args;
use console::style;
use indicatif::{ProgressBar, ProgressStyle};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Args, Debug)]
pub struct DeployCommand {
    #[arg(short, long)]
    agent: String,
    
    #[arg(short, long)]
    version: String,
    
    #[arg(short, long)]
    environment: String,
    
    #[arg(long)]
    control_plane: Option<String>,
    
    #[arg(long)]
    replicas: Option<u32>,
    
    #[arg(long)]
    auto_scale: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DeploymentRequest {
    pub agent_name: String,
    pub agent_version: String,
    pub environment: String,
    pub replicas: u32,
    pub auto_scale: bool,
    pub resources: ResourceRequirements,
    pub secrets: Vec<String>,
    pub config: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ResourceRequirements {
    pub cpu_millicores: u32,
    pub memory_mb: u32,
    pub max_execution_time_ms: u64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct DeploymentResponse {
    pub deployment_id: String,
    pub status: String,
    pub endpoint: Option<String>,
    pub created_at: String,
}

impl DeployCommand {
    pub async fn execute(&self, config: &crate::RuntimeConfig) -> Result<()> {
        let control_plane = self.control_plane.clone().unwrap_or_else(|| {
            config.server.control_plane_url.clone().unwrap_or_else(|| "https://api.ari.io".to_string())
        });
        
        println!("{} Deploying agent to control plane", style("→").blue());
        println!("  Agent:       {}:{}", self.agent, self.version);
        println!("  Environment: {}", self.environment);
        println!("  Control:     {}", control_plane);
        
        let pb = ProgressBar::new(4);
        pb.set_style(ProgressStyle::default_bar()
            .template("{spinner:.green} [{bar:40.cyan/blue}] {pos}/{len} {msg}")
            .unwrap()
            .progress_chars("##-"));
        
        // Step 1: Verify agent exists in registry
        pb.set_message("Verifying agent in registry...");
        self.verify_agent(&control_plane).await?;
        pb.inc(1);
        
        // Step 2: Create deployment
        pb.set_message("Creating deployment...");
        let deployment = self.create_deployment(&control_plane).await?;
        pb.inc(1);
        
        // Step 3: Wait for ready
        pb.set_message("Waiting for deployment to be ready...");
        self.wait_for_ready(&control_plane, &deployment.deployment_id).await?;
        pb.inc(1);
        
        // Step 4: Health check
        pb.set_message("Running health checks...");
        self.health_check(&control_plane, &deployment.deployment_id).await?;
        pb.inc(1);
        
        pb.finish_with_message("Deployment complete!");
        
        println!("\n{} Agent deployed successfully!", style("✓").green());
        println!("  Deployment ID: {}", deployment.deployment_id);
        println!("  Status:        {}", deployment.status);
        if let Some(endpoint) = deployment.endpoint {
            println!("  Endpoint:      {}", endpoint);
        }
        
        Ok(())
    }
    
    async fn verify_agent(&self, control_plane: &str) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/agents/{}/{}", control_plane, self.agent, self.version);
        
        let resp = client.get(&url).send().await?;
        
        if !resp.status().is_success() {
            return Err(anyhow::anyhow!("Agent not found in registry: {}:{}", self.agent, self.version));
        }
        
        Ok(())
    }
    
    async fn create_deployment(&self, control_plane: &str) -> Result<DeploymentResponse> {
        let client = Client::new();
        let url = format!("{}/api/v1/deployments", control_plane);
        
        let request = DeploymentRequest {
            agent_name: self.agent.clone(),
            agent_version: self.version.clone(),
            environment: self.environment.clone(),
            replicas: self.replicas.unwrap_or(1),
            auto_scale: self.auto_scale,
            resources: ResourceRequirements {
                cpu_millicores: 500,
                memory_mb: 512,
                max_execution_time_ms: 300_000,
            },
            secrets: vec![],
            config: serde_json::json!({}),
        };
        
        let resp = client
            .post(&url)
            .json(&request)
            .send()
            .await?;
        
        if !resp.status().is_success() {
            let err = resp.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("Deployment creation failed: {}", err));
        }
        
        let deployment: DeploymentResponse = resp.json().await?;
        Ok(deployment)
    }
    
    async fn wait_for_ready(&self, control_plane: &str, deployment_id: &str) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/deployments/{}", control_plane, deployment_id);
        
        for _ in 0..60 {
            let resp = client.get(&url).send().await?;
            
            if resp.status().is_success() {
                let deployment: DeploymentResponse = resp.json().await?;
                if deployment.status == "ready" {
                    return Ok(());
                }
                if deployment.status == "failed" {
                    return Err(anyhow::anyhow!("Deployment failed"));
                }
            }
            
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        }
        
        Err(anyhow::anyhow!("Deployment timed out"))
    }
    
    async fn health_check(&self, control_plane: &str, deployment_id: &str) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/deployments/{}/health", control_plane, deployment_id);
        
        let resp = client.get(&url).send().await?;
        
        if !resp.status().is_success() {
            return Err(anyhow::anyhow!("Health check failed"));
        }
        
        Ok(())
    }
}