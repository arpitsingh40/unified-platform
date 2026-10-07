//! Configuration for ARI Runtime

use anyhow::Result;
use figment::{Figment, providers::{Env, Format, Toml}, Profile};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeConfig {
    pub server: ServerConfig,
    pub runtime: RuntimeEngineConfig,
    pub governance: GovernanceConfig,
    pub capabilities: CapabilitiesConfig,
    pub memory: MemoryConfig,
    pub telemetry: TelemetryConfig,
    pub storage: StorageConfig,
    pub identity: IdentityConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
    pub control_plane_url: Option<String>,
    pub tls_cert: Option<PathBuf>,
    pub tls_key: Option<PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeEngineConfig {
    pub wasm_cache_dir: PathBuf,
    pub max_concurrent_agents: usize,
    pub default_execution_timeout_ms: u64,
    pub default_memory_limit_mb: u32,
    pub fuel_limit: Option<u64>,
    pub epoch_interruption: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernanceConfig {
    pub kill_switch_enabled: bool,
    pub dry_run_default: bool,
    pub default_weekly_cap_usd: f64,
    pub governance_state_db: String,
    pub org_governance_db: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilitiesConfig {
    pub registry_url: String,
    pub builtin_capabilities: Vec<String>,
    pub capability_timeout_ms: u64,
    pub max_retries: u32,
    pub retry_base_delay_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryConfig {
    pub backend: MemoryBackend,
    pub redis_url: Option<String>,
    pub postgres_url: Option<String>,
    pub encryption_key: Option<String>,
    pub ttl_seconds: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MemoryBackend {
    InMemory,
    Redis,
    Postgres,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TelemetryConfig {
    pub tracing_level: String,
    pub otel_endpoint: Option<String>,
    pub metrics_port: u16,
    pub log_json: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StorageConfig {
    pub postgres_url: String,
    pub pool_size: u32,
    pub migration_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityConfig {
    pub ca_cert: PathBuf,
    pub ca_key: PathBuf,
    pub cert_ttl_days: u32,
    pub key_algorithm: String,
}

impl RuntimeConfig {
    pub fn load(path: &str) -> Result<Self> {
        let config: RuntimeConfig = Figment::new()
            .merge(Toml::file(path).nested())
            .merge(Env::prefixed("ARI_").global())
            .select(Profile::from(std::env::var("ARI_ENV").unwrap_or_else(|_| "development".into())))
            .extract()?;
        Ok(config)
    }
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            server: ServerConfig {
                host: "0.0.0.0".into(),
                port: 8080,
                control_plane_url: None,
                tls_cert: None,
                tls_key: None,
            },
            runtime: RuntimeEngineConfig {
                wasm_cache_dir: "./cache/wasm".into(),
                max_concurrent_agents: 100,
                default_execution_timeout_ms: 300_000,
                default_memory_limit_mb: 512,
                fuel_limit: Some(10_000_000),
                epoch_interruption: true,
            },
            governance: GovernanceConfig {
                kill_switch_enabled: false,
                dry_run_default: true,
                default_weekly_cap_usd: 100.0,
                governance_state_db: "governance_state".into(),
                org_governance_db: "org_governance".into(),
            },
            capabilities: CapabilitiesConfig {
                registry_url: "https://registry.ari.io".into(),
                builtin_capabilities: vec!["http".into(), "email".into(), "crm".into()],
                capability_timeout_ms: 30_000,
                max_retries: 3,
                retry_base_delay_ms: 2000,
            },
            memory: MemoryConfig {
                backend: MemoryBackend::InMemory,
                redis_url: None,
                postgres_url: None,
                encryption_key: None,
                ttl_seconds: Some(86400 * 30),
            },
            telemetry: TelemetryConfig {
                tracing_level: "info".into(),
                otel_endpoint: None,
                metrics_port: 9090,
                log_json: true,
            },
            storage: StorageConfig {
                postgres_url: "postgresql://localhost/ari".into(),
                pool_size: 10,
                migration_dir: "./migrations".into(),
            },
            identity: IdentityConfig {
                ca_cert: "./certs/ca.pem".into(),
                ca_key: "./certs/ca.key".into(),
                cert_ttl_days: 90,
                key_algorithm: "ed25519".into(),
            },
        }
    }
}