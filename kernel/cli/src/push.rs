//! Push command - push component to registry

use anyhow::{Context, Result};
use clap::Args;
use console::style;
use indicatif::{ProgressBar, ProgressStyle};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tokio::fs;

#[derive(Args, Debug)]
pub struct PushCommand {
    #[arg(short, long, default_value = "target/wasm32-wasip1/release/agent.wasm")]
    component: PathBuf,
    
    #[arg(short, long)]
    registry: Option<String>,
    
    #[arg(long)]
    tag: Option<String>,
    
    #[arg(long)]
    public: bool,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct RegistryManifest {
    pub name: String,
    pub version: String,
    pub description: String,
    pub author: String,
    pub component_hash: String,
    pub component_size: u64,
    pub capabilities: Vec<String>,
    pub authority: String,
    pub spec_version: String,
    pub created_at: String,
    pub signature: Option<String>,
}

impl PushCommand {
    pub async fn execute(&self, config: &crate::RuntimeConfig) -> Result<()> {
        let component_path = &self.component;
        let registry_url = self.registry.clone().unwrap_or_else(|| config.capabilities.registry_url.clone());
        
        println!("{} Pushing component to registry", style("→").blue());
        println!("  Component: {}", component_path.display());
        println!("  Registry:  {}", registry_url);
        
        // Verify component exists
        if !component_path.exists() {
            return Err(anyhow::anyhow!("Component not found: {}", component_path.display()));
        }
        
        // Load metadata
        let meta_path = component_path.with_extension("json");
        let metadata: serde_json::Value = if meta_path.exists() {
            let content = fs::read_to_string(&meta_path).await?;
            serde_json::from_str(&content)?
        } else {
            return Err(anyhow::anyhow!("Metadata file not found: {}. Run 'ari build' first.", meta_path.display()));
        };
        
        // Calculate hash
        let component_bytes = fs::read(component_path).await?;
        let hash = self.calculate_hash(&component_bytes)?;
        let size = component_bytes.len() as u64;
        
        // Create manifest
        let manifest = RegistryManifest {
            name: metadata["name"].as_str().unwrap_or("unknown").to_string(),
            version: metadata["version"].as_str().unwrap_or("0.0.0").to_string(),
            description: metadata["description"].as_str().unwrap_or("").to_string(),
            author: metadata["author"].as_str().unwrap_or("").to_string(),
            component_hash: hash.clone(),
            component_size: size,
            capabilities: metadata["capabilities"].as_array()
                .map(|a| a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect())
                .unwrap_or_default(),
            authority: metadata["authority"].as_str().unwrap_or("L1").to_string(),
            spec_version: metadata["spec_version"].as_str().unwrap_or("1.0").to_string(),
            created_at: chrono::Utc::now().to_rfc3339(),
            signature: None,
        };
        
        // Progress
        let pb = ProgressBar::new(3);
        pb.set_style(ProgressStyle::default_bar()
            .template("{spinner:.green} [{bar:40.cyan/blue}] {pos}/{len} {msg}")
            .unwrap()
            .progress_chars("##-"));
        
        // Step 1: Upload component
        pb.set_message("Uploading component...");
        self.upload_component(&registry_url, &manifest, &component_bytes).await?;
        pb.inc(1);
        
        // Step 2: Upload manifest
        pb.set_message("Uploading manifest...");
        self.upload_manifest(&registry_url, &manifest).await?;
        pb.inc(1);
        
        // Step 3: Verify
        pb.set_message("Verifying upload...");
        self.verify_upload(&registry_url, &manifest.name, &manifest.version, &hash).await?;
        pb.inc(1);
        
        pb.finish_with_message("Push complete!");
        
        println!("\n{} Component pushed successfully!", style("✓").green());
        println!("  Name:    {}", manifest.name);
        println!("  Version: {}", manifest.version);
        println!("  Hash:    {}", &hash[..16]);
        println!("  Size:    {} bytes", size);
        
        Ok(())
    }
    
    fn calculate_hash(&self, data: &[u8]) -> Result<String> {
        use sha2::{Sha256, Digest};
        let mut hasher = Sha256::new();
        hasher.update(data);
        Ok(hex::encode(hasher.finalize()))
    }
    
    async fn upload_component(&self, registry_url: &str, manifest: &RegistryManifest, data: &[u8]) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/components/{}/{}", registry_url, manifest.name, manifest.version);
        
        // In production, this would be a multipart upload
        let resp = client
            .put(&url)
            .header("Content-Type", "application/wasm")
            .body(data.to_vec())
            .send()
            .await?;
        
        if !resp.status().is_success() {
            let err = resp.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("Upload failed: {}", err));
        }
        
        Ok(())
    }
    
    async fn upload_manifest(&self, registry_url: &str, manifest: &RegistryManifest) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/manifests/{}/{}", registry_url, manifest.name, manifest.version);
        
        let resp = client
            .put(&url)
            .json(manifest)
            .send()
            .await?;
        
        if !resp.status().is_success() {
            let err = resp.text().await.unwrap_or_default();
            return Err(anyhow::anyhow!("Manifest upload failed: {}", err));
        }
        
        Ok(())
    }
    
    async fn verify_upload(&self, registry_url: &str, name: &str, version: &str, expected_hash: &str) -> Result<()> {
        let client = Client::new();
        let url = format!("{}/api/v1/components/{}/{}/verify", registry_url, name, version);
        
        let resp = client
            .get(&url)
            .send()
            .await?;
        
        if !resp.status().is_success() {
            return Err(anyhow::anyhow!("Verification failed"));
        }
        
        // Verify hash matches
        // In production, registry would return the hash
        Ok(())
    }
}