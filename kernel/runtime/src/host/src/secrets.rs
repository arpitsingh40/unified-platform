//! Per-org secrets vault — encrypted at rest (AES-GCM with random nonce per value).

use anyhow::{Context, Result};
use std::collections::HashMap;

fn parse_key(hex_str: &str) -> Result<[u8;32]> {
    let b = hex::decode(hex_str.trim()).context("invalid hex key")?;
    if b.len() < 32 { anyhow::bail!("key must be 32 bytes (64 hex chars), got {}", b.len()); }
    let mut out=[0u8;32]; out.copy_from_slice(&b[..32]); Ok(out)
}

fn key_from_env_or_cfg(cfg_key: Option<&str>) -> Option<[u8;32]> {
    let raw = cfg_key.map(|s| s.to_string())
        .or_else(|| std::env::var("ARI_MEMORY_ENCRYPTION_KEY").ok())
        .or_else(|| std::env::var("ARI_SECRETS_KEY").ok());
    raw.and_then(|s| parse_key(&s).ok())
}

fn encrypt(key: Option<[u8;32]>, pt: &[u8]) -> Result<Vec<u8>> {
    if let Some(k) = key {
        use aes_gcm::{Aes256Gcm, Key, Nonce, aead::Aead, KeyInit};
        use rand::RngCore;
        let cipher = Aes256Gcm::new(Key::<aes_gcm::Aes256Gcm>::from_slice(&k));
        let mut nb=[0u8;12]; rand::thread_rng().fill_bytes(&mut nb);
        let ct = cipher.encrypt(Nonce::from_slice(&nb), pt).map_err(|e| anyhow::anyhow!("encrypt: {}", e))?;
        let mut out = nb.to_vec(); out.extend_from_slice(&ct); Ok(out)
    } else { Ok(pt.to_vec()) }
}
fn decrypt(key: Option<[u8;32]>, data: &[u8]) -> Result<Vec<u8>> {
    if let Some(k) = key {
        use aes_gcm::{Aes256Gcm, Key, Nonce, aead::Aead, KeyInit};
        if data.len() < 12 { anyhow::bail!("ciphertext too short"); }
        let (nb, ct) = data.split_at(12);
        let cipher = Aes256Gcm::new(Key::<aes_gcm::Aes256Gcm>::from_slice(&k));
        Ok(cipher.decrypt(Nonce::from_slice(nb), ct).map_err(|e| anyhow::anyhow!("decrypt: {}", e))?)
    } else { Ok(data.to_vec()) }
}

pub struct SecretsManager {
    pool: sqlx::PgPool,
    key: Option<[u8;32]>,
}

impl SecretsManager {
    pub fn new(pool: sqlx::PgPool, cfg_key: Option<String>) -> Self {
        let key = key_from_env_or_cfg(cfg_key.as_deref());
        Self { pool, key }
    }

    pub async fn set_secret(&self, org_id:&str, name:&str, plaintext:&str) -> Result<()> {
        let enc = encrypt(self.key, plaintext.as_bytes())?;
        sqlx::query("INSERT INTO secrets (org_id, name, encrypted_value) VALUES ($1,$2,$3) ON CONFLICT (org_id, name) DO UPDATE SET encrypted_value=EXCLUDED.encrypted_value, updated_at=NOW()")
            .bind(org_id).bind(name).bind(&enc).execute(&self.pool).await?;
        Ok(())
    }

    pub async fn get_secret(&self, org_id:&str, name:&str) -> Result<Option<String>> {
        let row: Option<(Vec<u8>,)> = sqlx::query_as("SELECT encrypted_value FROM secrets WHERE org_id=$1 AND name=$2")
            .bind(org_id).bind(name).fetch_optional(&self.pool).await?;
        match row {
            Some((enc,)) => { let pt = decrypt(self.key, &enc)?; Ok(Some(String::from_utf8(pt).context("secret not utf8")?)) },
            None => Ok(None),
        }
    }

    pub async fn delete_secret(&self, org_id:&str, name:&str) -> Result<bool> {
        let r = sqlx::query("DELETE FROM secrets WHERE org_id=$1 AND name=$2").bind(org_id).bind(name).execute(&self.pool).await?;
        Ok(r.rows_affected()>0)
    }

    pub async fn list_secret_names(&self, org_id:&str) -> Result<Vec<String>> {
        let rows: Vec<(String,)> = sqlx::query_as("SELECT name FROM secrets WHERE org_id=$1 ORDER BY name").bind(org_id).fetch_all(&self.pool).await?;
        Ok(rows.into_iter().map(|(n,)| n).collect())
    }

    /// Replace ${NAME} placeholders using a pre-fetched cache. Missing keys are left as-is.
    pub fn resolve_placeholders(&self, input: &str, _org_id:&str, cache: &HashMap<String,String>) -> String {
        let mut out = input.to_string();
        for (k,v) in cache {
            out = out.replace(&format!("${{{}}}", k), v);
            out = out.replace(&format!("${}", k), v);
        }
        out
    }

    /// Fetch all secrets for an org into a HashMap (single query).
    pub async fn load_org_cache(&self, org_id:&str) -> Result<HashMap<String,String>> {
        let rows: Vec<(String, Vec<u8>)> = sqlx::query_as("SELECT name, encrypted_value FROM secrets WHERE org_id=$1")
            .bind(org_id).fetch_all(&self.pool).await?;
        let mut m=HashMap::new();
        for (name, enc) in rows {
            if let Ok(pt) = decrypt(self.key, &enc) {
                if let Ok(s) = String::from_utf8(pt) { m.insert(name, s); }
            }
        }
        Ok(m)
    }
}
