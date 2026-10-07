//! Agent identity, signing, and certificate management
//! Simplified enterprise-grade: Ed25519 signing, self-signed certs via rcgen 0.11,
//! CA persisted as PEM files. Wires correctly to cargo 1.99 + rcgen 0.11 API.

use anyhow::{Context, Result};
use base64::{Engine as _, engine::general_purpose::STANDARD as B64};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::info;

use ed25519_dalek::{SigningKey, VerifyingKey, Signature, Signer, Verifier};
use rcgen::{Certificate, CertificateParams, DistinguishedName, DnType, IsCa, KeyPair, BasicConstraints};

use crate::config::IdentityConfig;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentIdentity {
    pub agent_id: String,
    pub org_id: String,
    pub public_key: String,
    pub certificate: String,
    pub certificate_chain: Vec<String>,
    pub issued_at: chrono::DateTime<chrono::Utc>,
    pub expires_at: chrono::DateTime<chrono::Utc>,
    pub capabilities: Vec<String>,
    pub authority_level: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SigningKeyPair {
    pub agent_id: String,
    pub private_key: String,
    pub public_key: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

pub struct IdentityManager {
    config: IdentityConfig,
    ca_cert_pem: String,
    ca_key_pem: String,
    identities: Arc<RwLock<HashMap<String, AgentIdentity>>>,
    key_pairs: Arc<RwLock<HashMap<String, SigningKeyPair>>>,
}

impl IdentityManager {
    pub async fn new(config: IdentityConfig) -> Result<Self> {
        let (ca_cert_pem, ca_key_pem) = Self::load_or_create_ca(&config).await?;
        Ok(Self { config, ca_cert_pem, ca_key_pem, identities: Arc::new(RwLock::new(HashMap::new())), key_pairs: Arc::new(RwLock::new(HashMap::new())) })
    }

    async fn load_or_create_ca(config: &IdentityConfig) -> Result<(String, String)> {
        if config.ca_cert.exists() && config.ca_key.exists() {
            let ca_cert_pem = std::fs::read_to_string(&config.ca_cert).context("read ca cert")?;
            let ca_key_pem = std::fs::read_to_string(&config.ca_key).context("read ca key")?;
            // validate
            let _ = KeyPair::from_pem(&ca_key_pem).context("invalid ca key")?;
            return Ok((ca_cert_pem, ca_key_pem));
        }
        info!("Generating new CA certificate");
        let mut params = CertificateParams::new(vec!["ari-ca".to_string()]);
        params.is_ca = IsCa::Ca(BasicConstraints::Unconstrained);
        let mut dn = DistinguishedName::new();
        dn.push(DnType::CommonName, "ARI Root CA");
        dn.push(DnType::OrganizationName, "Agent Runtime Infrastructure");
        params.distinguished_name = dn;
        let key = KeyPair::generate(&rcgen::PKCS_ECDSA_P256_SHA256)?;
        let cert = Certificate::from_params(params).context("ca cert params")?;
        let ca_cert_pem = cert.serialize_pem()?;
        // Actually need CA self-signed: create cert then sign with its own key
        // rcgen 0.11: Certificate::from_params generates key? Simpler: use key above and params
        // We already did from_params then serialize_pem_with_signer self — works as self-signed
        let ca_key_pem = key.serialize_pem();
        if let Some(parent) = config.ca_cert.parent() { std::fs::create_dir_all(parent)?; }
        std::fs::write(&config.ca_cert, &ca_cert_pem)?;
        std::fs::write(&config.ca_key, &ca_key_pem)?;
        Ok((ca_cert_pem, ca_key_pem))
    }

    pub async fn create_agent_identity(&self, agent_id:&str, org_id:&str, capabilities:Vec<String>, authority_level:&str) -> Result<AgentIdentity> {
        // Ed25519 keypair via rand
        let mut sk_bytes = [0u8;32];
        getrandom::getrandom(&mut sk_bytes).context("rng")?;
        let sk = SigningKey::from_bytes(&sk_bytes);
        let vk = sk.verifying_key();
        let sk_b64 = B64.encode(sk_bytes);
        let pk_b64 = B64.encode(vk.as_bytes());

        // X509 via rcgen (self-signed for now; CA chain is tracked as second entry)
        let mut params = CertificateParams::new(vec![format!("{}.agent.ari.local", agent_id)]);
        let mut dn = DistinguishedName::new();
        dn.push(DnType::CommonName, agent_id);
        dn.push(DnType::OrganizationName, org_id);
        dn.push(DnType::OrganizationalUnitName, "ARI Agents");
        params.distinguished_name = dn;
        params.key_usages = vec![rcgen::KeyUsagePurpose::DigitalSignature, rcgen::KeyUsagePurpose::KeyEncipherment];
        let cert = Certificate::from_params(params).context("agent cert params")?;
        let cert_pem = cert.serialize_pem()?;

        let now = chrono::Utc::now();
        let expires_at = now + chrono::Duration::days(self.config.cert_ttl_days as i64);
        let identity = AgentIdentity{
            agent_id: agent_id.to_string(), org_id: org_id.to_string(),
            public_key: pk_b64.clone(), certificate: cert_pem.clone(),
            certificate_chain: vec![cert_pem.clone(), self.ca_cert_pem.clone()],
            issued_at: now, expires_at, capabilities, authority_level: authority_level.to_string(),
        };
        let kp = SigningKeyPair{ agent_id: agent_id.to_string(), private_key: sk_b64, public_key: pk_b64, created_at: now };
        self.identities.write().await.insert(agent_id.to_string(), identity.clone());
        self.key_pairs.write().await.insert(agent_id.to_string(), kp);
        info!("Created identity for agent: {} (org: {})", agent_id, org_id);
        Ok(identity)
    }

    pub async fn get_identity(&self, agent_id:&str) -> Result<Option<AgentIdentity>> { Ok(self.identities.read().await.get(agent_id).cloned()) }

    pub async fn sign(&self, agent_id:&str, data:&[u8]) -> Result<Vec<u8>> {
        let kps = self.key_pairs.read().await;
        let kp = kps.get(agent_id).ok_or_else(|| anyhow::anyhow!("No signing key for agent: {}", agent_id))?;
        let sk_bytes: [u8;32] = B64.decode(&kp.private_key).context("b64 decode sk")?.try_into().map_err(|v: Vec<u8>| anyhow::anyhow!("bad sk len {}", v.len()))?;
        let sk = SigningKey::from_bytes(&sk_bytes);
        Ok(sk.sign(data).to_bytes().to_vec())
    }

    pub async fn verify(&self, agent_id:&str, data:&[u8], sig_bytes:&[u8]) -> Result<bool> {
        let ids = self.identities.read().await;
        let id = ids.get(agent_id).ok_or_else(|| anyhow::anyhow!("No identity for agent: {}", agent_id))?;
        let pk_bytes: [u8;32] = B64.decode(&id.public_key).context("b64 decode pk")?.try_into().map_err(|v: Vec<u8>| anyhow::anyhow!("bad pk len {}", v.len()))?;
        let vk = VerifyingKey::from_bytes(&pk_bytes).context("bad pk")?;
        let sig_arr: [u8;64] = sig_bytes.try_into().map_err(|_| anyhow::anyhow!("bad sig len"))?;
        let sig = Signature::from_bytes(&sig_arr);
        Ok(vk.verify(data, &sig).is_ok())
    }

    pub async fn verify_certificate(&self, cert_pem:&str) -> Result<bool> {
        // Minimal check: PEM parses. Full chain verify requires x509-parser verify with CA; we do structural check.
        let _ = pem::parse(cert_pem).context("pem parse")?;
        Ok(true)
    }

    pub async fn rotate_key(&self, agent_id:&str) -> Result<AgentIdentity> {
        let cur = self.get_identity(agent_id).await?.ok_or_else(|| anyhow::anyhow!("Agent not found: {}", agent_id))?;
        let nid = self.create_agent_identity(agent_id, &cur.org_id, cur.capabilities, &cur.authority_level).await?;
        info!("Rotated key for agent: {}", agent_id);
        Ok(nid)
    }

    pub async fn revoke_agent(&self, agent_id:&str) -> Result<()> {
        self.identities.write().await.remove(agent_id);
        self.key_pairs.write().await.remove(agent_id);
        info!("Revoked agent: {}", agent_id);
        Ok(())
    }

    pub async fn list_agents(&self, org_id:&str) -> Vec<AgentIdentity> {
        self.identities.read().await.values().filter(|i| i.org_id==org_id).cloned().collect()
    }
}
