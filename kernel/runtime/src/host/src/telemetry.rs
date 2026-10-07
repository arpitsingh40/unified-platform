//! Telemetry initialization — idempotent. OTEL optional.

use anyhow::Result;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};
use std::sync::OnceLock;

static INIT: OnceLock<()> = OnceLock::new();

pub fn init_telemetry() -> Result<()> {
    if INIT.get().is_none() {
        let env_filter = EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| EnvFilter::new("info,ari_runtime=debug"));
        let _ = tracing_subscriber::registry()
            .with(env_filter)
            .with(tracing_subscriber::fmt::layer().json())
            .try_init();
        let _ = INIT.set(());
    }
    Ok(())
}

/// If `TelemetryConfig.otel_endpoint` is set, configure an OTLP exporter via
/// `opentelemetry_otlp` if the feature is enabled. Otherwise this is a no-op
/// and tracing stays local-only. Call from `lib.rs` after `init_telemetry()`
/// when `config.telemetry.otel_endpoint` is Some.
pub fn maybe_init_otel(endpoint: Option<&str>) -> Result<()> {
    let Some(ep) = endpoint else { return Ok(()); };
    if ep.trim().is_empty() { return Ok(()); }
    // Keep crate graph minimal: if `opentelemetry-otlp` is not enabled, just log.
    // To enable: add `opentelemetry`, `opentelemetry-otlp`, `tracing-opentelemetry` to Cargo.toml
    // and feature `otel` below.
    #[cfg(feature = "otel")]
    {
        use opentelemetry::global;
        use opentelemetry_otlp::WithExportConfig as _;
        use tracing_opentelemetry::OpenTelemetryLayer;
        let tracer = opentelemetry_otlp::new_pipeline()
            .tracing()
            .with_exporter(opentelemetry_otlp::new_exporter().tonic().with_endpoint(ep.to_string()))
            .with_trace_config(opentelemetry::sdk::trace::config().with_resource(opentelemetry::sdk::Resource::new(vec![
                opentelemetry::KeyValue::new("service.name", "ari-runtime-host"),
            ])))
            .install_batch(opentelemetry::runtime::Tokio)?;
        let _ = global::set_tracer_provider(tracer.provider().unwrap().clone());
        tracing::info!(endpoint=%ep, "OTEL exporter configured");
        let _ = (ep, OpenTelemetryLayer::new as fn(_) -> _); // suppress unused warning when feature off
    }
    #[cfg(not(feature = "otel"))]
    {
        tracing::info!(endpoint=%ep, "otel_endpoint set but `otel` feature not enabled — run with --features otel to export traces");
    }
    Ok(())
}
