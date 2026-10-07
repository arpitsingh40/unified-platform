//! Persistent agent memory with encryption, TTL, multiple backends
//! Enterprise fixes: dynamic sqlx queries (offline-buildable), random nonce per-encrypt,
//! proper trait dispatch via enum, correct redis async generics.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::config::{MemoryConfig, MemoryBackend as MemoryBackendCfg};

// ---------------------------------------------------------------------------
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub key: String,
    pub value: serde_json::Value,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub updated_at: chrono::DateTime<chrono::Utc>,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
    pub version: u64,
    pub tags: Vec<String>,
}

// Trait uses async_trait for dyn compatibility
#[async_trait::async_trait]
pub trait MemoryBackend: Send + Sync {
    async fn set(&self, agent_id: &str, entry: MemoryEntry) -> Result<()>;
    async fn get(&self, agent_id: &str, key: &str) -> Result<Option<MemoryEntry>>;
    async fn delete(&self, agent_id: &str, key: &str) -> Result<bool>;
    async fn list(&self, agent_id: &str, prefix: &str) -> Result<Vec<MemoryEntry>>;
    async fn exists(&self, agent_id: &str, key: &str) -> Result<bool>;
    async fn clear_agent(&self, agent_id: &str) -> Result<u64>;
    async fn cleanup_expired(&self) -> Result<u64>;
}

// ─── helpers: encryption with random nonce per value ──────────────────────
fn encrypt_value(encryption_key: Option<[u8; 32]>, plaintext: &[u8]) -> Result<Vec<u8>> {
    if let Some(key) = encryption_key {
        use aes_gcm::{Aes256Gcm, Key, Nonce, aead::Aead, KeyInit};
        use rand::RngCore;
        let cipher = Aes256Gcm::new(Key::<aes_gcm::Aes256Gcm>::from_slice(&key));
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        let mut ciphertext = cipher.encrypt(nonce, plaintext).map_err(|e| anyhow::anyhow!("encrypt failed: {}", e))?;
        // prepend nonce so decrypt can recover it
        let mut out = nonce_bytes.to_vec();
        out.append(&mut ciphertext);
        Ok(out)
    } else {
        Ok(plaintext.to_vec())
    }
}

fn decrypt_value(encryption_key: Option<[u8; 32]>, data: &[u8]) -> Result<Vec<u8>> {
    if let Some(key) = encryption_key {
        use aes_gcm::{Aes256Gcm, Key, Nonce, aead::Aead, KeyInit};
        if data.len() < 12 {
            anyhow::bail!("ciphertext too short");
        }
        let (nonce_bytes, ct) = data.split_at(12);
        let cipher = Aes256Gcm::new(Key::<aes_gcm::Aes256Gcm>::from_slice(&key));
        let nonce = Nonce::from_slice(nonce_bytes);
        Ok(cipher.decrypt(nonce, ct).map_err(|e| anyhow::anyhow!("decrypt failed: {}", e))?)
    } else {
        Ok(data.to_vec())
    }
}

// ─── InMemoryBackend ──────────────────────────────────────────────────────
pub struct InMemoryBackend {
    data: Arc<RwLock<HashMap<String, HashMap<String, MemoryEntry>>>>,
}

impl InMemoryBackend {
    pub fn new() -> Self {
        Self { data: Arc::new(RwLock::new(HashMap::new())) }
    }
}

#[async_trait::async_trait]
impl MemoryBackend for InMemoryBackend {
    async fn set(&self, agent_id: &str, entry: MemoryEntry) -> Result<()> {
        let mut data = self.data.write().await;
        data.entry(agent_id.to_string()).or_insert_with(HashMap::new).insert(entry.key.clone(), entry);
        Ok(())
    }
    async fn get(&self, agent_id: &str, key: &str) -> Result<Option<MemoryEntry>> {
        let data = self.data.read().await;
        // honour TTL
        if let Some(e) = data.get(agent_id).and_then(|m| m.get(key).cloned()) {
            if e.expires_at.map(|exp| exp < chrono::Utc::now()).unwrap_or(false) {
                drop(data);
                self.delete(agent_id, key).await?;
                return Ok(None);
            }
            Ok(Some(e))
        } else {
            Ok(None)
        }
    }
    async fn delete(&self, agent_id: &str, key: &str) -> Result<bool> {
        Ok(self.data.write().await.get_mut(agent_id).map(|m| m.remove(key).is_some()).unwrap_or(false))
    }
    async fn list(&self, agent_id: &str, prefix: &str) -> Result<Vec<MemoryEntry>> {
        let now = chrono::Utc::now();
        let data = self.data.read().await;
        Ok(data.get(agent_id).map(|m| m.values().filter(|e| e.key.starts_with(prefix) && e.expires_at.map(|exp| exp > now).unwrap_or(true)).cloned().collect()).unwrap_or_default())
    }
    async fn exists(&self, agent_id: &str, key: &str) -> Result<bool> {
        Ok(self.get(agent_id, key).await?.is_some())
    }
    async fn clear_agent(&self, agent_id: &str) -> Result<u64> {
        Ok(self.data.write().await.remove(agent_id).map(|m| m.len() as u64).unwrap_or(0))
    }
    async fn cleanup_expired(&self) -> Result<u64> {
        let mut data = self.data.write().await;
        let now = chrono::Utc::now();
        let mut n = 0u64;
        for m in data.values_mut() {
            let dead: Vec<String> = m.iter().filter(|(_, e)| e.expires_at.map(|exp| exp < now).unwrap_or(false)).map(|(k,_)| k.clone()).collect();
            for k in dead { m.remove(&k); n+=1; }
        }
        Ok(n)
    }
}

// ─── RedisBackend ─────────────────────────────────────────────────────────
pub struct RedisBackend {
    client: redis::Client,
    key_prefix: String,
    encryption_key: Option<[u8; 32]>,
}

impl RedisBackend {
    pub fn new(url: &str, key_prefix: &str, encryption_key: Option<[u8; 32]>) -> Result<Self> {
        Ok(Self { client: redis::Client::open(url)?, key_prefix: key_prefix.to_string(), encryption_key })
    }
    fn rkey(&self, agent_id: &str, key: &str) -> String { format!("{}:agent:{}:{}", self.key_prefix, agent_id, key) }
    fn enc(&self, v: &[u8]) -> Result<Vec<u8>> { encrypt_value(self.encryption_key, v) }
    fn dec(&self, v: &[u8]) -> Result<Vec<u8>> { decrypt_value(self.encryption_key, v) }
}

#[async_trait::async_trait]
impl MemoryBackend for RedisBackend {
    async fn set(&self, agent_id: &str, entry: MemoryEntry) -> Result<()> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let k = self.rkey(agent_id, &entry.key);
        let enc = self.enc(&serde_json::to_vec(&entry)?)?;
        let ttl = entry.expires_at.map(|e| (e - chrono::Utc::now()).num_seconds().max(0) as usize).unwrap_or(86400*30);
        let () = redis::cmd("SET").arg(&k).arg(&enc).arg("EX").arg(ttl).query_async(&mut conn).await?;
        Ok(())
    }
    async fn get(&self, agent_id: &str, key: &str) -> Result<Option<MemoryEntry>> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let rk = self.rkey(agent_id, key);
        let data: Option<Vec<u8>> = redis::cmd("GET").arg(&rk).query_async(&mut conn).await?;
        match data {
            Some(enc) => {
                let dec = self.dec(&enc)?;
                let e: MemoryEntry = serde_json::from_slice(&dec)?;
                if e.expires_at.map(|exp| exp < chrono::Utc::now()).unwrap_or(false) { self.delete(agent_id, key).await?; return Ok(None); }
                Ok(Some(e))
            }
            None => Ok(None),
        }
    }
    async fn delete(&self, agent_id: &str, key: &str) -> Result<bool> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let n: i64 = redis::cmd("DEL").arg(self.rkey(agent_id,key)).query_async(&mut conn).await?;
        Ok(n>0)
    }
    async fn list(&self, agent_id: &str, prefix: &str) -> Result<Vec<MemoryEntry>> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let pattern = self.rkey(agent_id, &format!("{}*", prefix));
        let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query_async(&mut conn).await?;
        let mut out = Vec::new();
        for k in keys {
            let data: Option<Vec<u8>> = redis::cmd("GET").arg(&k).query_async(&mut conn).await?;
            if let Some(enc) = data {
                if let Ok(dec) = self.dec(&enc) {
                    if let Ok(e) = serde_json::from_slice::<MemoryEntry>(&dec) {
                        if e.expires_at.map(|exp| exp > chrono::Utc::now()).unwrap_or(true) { out.push(e); }
                    }
                }
            }
        }
        Ok(out)
    }
    async fn exists(&self, agent_id: &str, key: &str) -> Result<bool> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let n: i64 = redis::cmd("EXISTS").arg(self.rkey(agent_id,key)).query_async(&mut conn).await?;
        Ok(n>0)
    }
    async fn clear_agent(&self, agent_id: &str) -> Result<u64> {
        let mut conn = self.client.get_multiplexed_tokio_connection().await?;
        let keys: Vec<String> = redis::cmd("KEYS").arg(self.rkey(agent_id,"*")).query_async(&mut conn).await?;
        if keys.is_empty() { return Ok(0); }
        let n: i64 = redis::cmd("DEL").arg(&keys).query_async(&mut conn).await?;
        Ok(n as u64)
    }
    async fn cleanup_expired(&self) -> Result<u64> { Ok(0) } // TTL handled by Redis
}

// ─── PostgresBackend — uses dynamic queries (offline-buildable) ──────────
pub struct PostgresBackend {
    pool: sqlx::PgPool,
    encryption_key: Option<[u8; 32]>,
}

impl PostgresBackend {
    pub fn new(pool: sqlx::PgPool, encryption_key: Option<[u8;32]>) -> Self { Self{pool, encryption_key} }
    fn enc(&self, v: &[u8]) -> Result<Vec<u8>> { encrypt_value(self.encryption_key, v) }
    fn dec(&self, v: &[u8]) -> Result<Vec<u8>> { decrypt_value(self.encryption_key, v) }
}

#[async_trait::async_trait]
impl MemoryBackend for PostgresBackend {
    async fn set(&self, agent_id: &str, entry: MemoryEntry) -> Result<()> {
        let enc = self.enc(&serde_json::to_vec(&entry)?)?;
        sqlx::query(
            "INSERT INTO agent_memory (agent_id, key, value, expires_at, version, tags) VALUES ($1,$2,$3,$4,$5,$6)
             ON CONFLICT (agent_id, key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW(), expires_at=EXCLUDED.expires_at, version=agent_memory.version+1, tags=EXCLUDED.tags"
        )
        .bind(agent_id).bind(&entry.key).bind(&enc).bind(entry.expires_at).bind(entry.version as i64).bind(&entry.tags)
        .execute(&self.pool).await?;
        Ok(())
    }
    async fn get(&self, agent_id: &str, key: &str) -> Result<Option<MemoryEntry>> {
        let row: Option<(Vec<u8>, Option<chrono::DateTime<chrono::Utc>>)> =
            sqlx::query_as("SELECT value, expires_at FROM agent_memory WHERE agent_id=$1 AND key=$2")
            .bind(agent_id).bind(key).fetch_optional(&self.pool).await?;
        match row {
            Some((enc, _)) => {
                let dec = self.dec(&enc)?;
                let e: MemoryEntry = serde_json::from_slice(&dec)?;
                if e.expires_at.map(|exp| exp < chrono::Utc::now()).unwrap_or(false) { self.delete(agent_id,key).await?; return Ok(None); }
                Ok(Some(e))
            }
            None => Ok(None),
        }
    }
    async fn delete(&self, agent_id: &str, key: &str) -> Result<bool> {
        let r = sqlx::query("DELETE FROM agent_memory WHERE agent_id=$1 AND key=$2").bind(agent_id).bind(key).execute(&self.pool).await?;
        Ok(r.rows_affected()>0)
    }
    async fn list(&self, agent_id: &str, prefix: &str) -> Result<Vec<MemoryEntry>> {
        let rows: Vec<(Vec<u8>,)> = sqlx::query_as("SELECT value FROM agent_memory WHERE agent_id=$1 AND key LIKE $2")
            .bind(agent_id).bind(format!("{}%", prefix)).fetch_all(&self.pool).await?;
        let now = chrono::Utc::now();
        let mut out = Vec::new();
        for (enc,) in rows {
            if let Ok(dec) = self.dec(&enc) {
                if let Ok(e) = serde_json::from_slice::<MemoryEntry>(&dec) {
                    if e.expires_at.map(|exp| exp > now).unwrap_or(true) { out.push(e); }
                }
            }
        }
        Ok(out)
    }
    async fn exists(&self, agent_id: &str, key: &str) -> Result<bool> {
        let row: Option<(i64,)> = sqlx::query_as("SELECT COUNT(*) FROM agent_memory WHERE agent_id=$1 AND key=$2")
            .bind(agent_id).bind(key).fetch_optional(&self.pool).await?;
        Ok(row.map(|(c,)| c>0).unwrap_or(false))
    }
    async fn clear_agent(&self, agent_id: &str) -> Result<u64> {
        let r = sqlx::query("DELETE FROM agent_memory WHERE agent_id=$1").bind(agent_id).execute(&self.pool).await?;
        Ok(r.rows_affected())
    }
    async fn cleanup_expired(&self) -> Result<u64> {
        let r = sqlx::query("DELETE FROM agent_memory WHERE expires_at < NOW()").execute(&self.pool).await?;
        Ok(r.rows_affected())
    }
}

// ─── Enum dispatch so MemoryManager doesn't need Box<dyn> ────────────────
enum BackendImpl { Memory(InMemoryBackend), Redis(RedisBackend), Postgres(PostgresBackend) }

#[async_trait::async_trait]
impl MemoryBackend for BackendImpl {
    async fn set(&self, a:&str,e:MemoryEntry)->Result<()> { match self { Self::Memory(b)=>b.set(a,e).await, Self::Redis(b)=>b.set(a,e).await, Self::Postgres(b)=>b.set(a,e).await } }
    async fn get(&self, a:&str,k:&str)->Result<Option<MemoryEntry>> { match self { Self::Memory(b)=>b.get(a,k).await, Self::Redis(b)=>b.get(a,k).await, Self::Postgres(b)=>b.get(a,k).await } }
    async fn delete(&self,a:&str,k:&str)->Result<bool>{ match self{Self::Memory(b)=>b.delete(a,k).await,Self::Redis(b)=>b.delete(a,k).await,Self::Postgres(b)=>b.delete(a,k).await} }
    async fn list(&self,a:&str,p:&str)->Result<Vec<MemoryEntry>>{ match self{Self::Memory(b)=>b.list(a,p).await,Self::Redis(b)=>b.list(a,p).await,Self::Postgres(b)=>b.list(a,p).await} }
    async fn exists(&self,a:&str,k:&str)->Result<bool>{ match self{Self::Memory(b)=>b.exists(a,k).await,Self::Redis(b)=>b.exists(a,k).await,Self::Postgres(b)=>b.exists(a,k).await} }
    async fn clear_agent(&self,a:&str)->Result<u64>{ match self{Self::Memory(b)=>b.clear_agent(a).await,Self::Redis(b)=>b.clear_agent(a).await,Self::Postgres(b)=>b.clear_agent(a).await} }
    async fn cleanup_expired(&self)->Result<u64>{ match self{Self::Memory(b)=>b.cleanup_expired().await,Self::Redis(b)=>b.cleanup_expired().await,Self::Postgres(b)=>b.cleanup_expired().await} }
}

pub struct MemoryManager {
    backend: BackendImpl,
    default_ttl: Option<u64>,
}

fn parse_encryption_key(hex_str: &str) -> Result<[u8;32]> {
    let bytes = hex::decode(hex_str.trim()).context("invalid hex encryption key")?;
    if bytes.len() < 32 { anyhow::bail!("encryption key must be 32 bytes (64 hex chars), got {}", bytes.len()); }
    let mut out = [0u8;32];
    out.copy_from_slice(&bytes[..32]);
    Ok(out)
}

impl MemoryManager {
    pub async fn new(config: MemoryConfig, pg_pool: Option<sqlx::PgPool>) -> Result<Self> {
        let enc_key = config.encryption_key.as_deref().map(parse_encryption_key).transpose()?;
        let backend = match config.backend {
            MemoryBackendCfg::InMemory => BackendImpl::Memory(InMemoryBackend::new()),
            MemoryBackendCfg::Redis => {
                let url = config.redis_url.ok_or_else(|| anyhow::anyhow!("Redis URL required"))?;
                BackendImpl::Redis(RedisBackend::new(&url, "ari", enc_key)?)
            }
            MemoryBackendCfg::Postgres => {
                let pool = pg_pool.ok_or_else(|| anyhow::anyhow!("Postgres pool required for Postgres backend"))?;
                BackendImpl::Postgres(PostgresBackend::new(pool, enc_key))
            }
        };
        Ok(Self{ backend, default_ttl: config.ttl_seconds })
    }
    pub async fn set(&self, agent_id:&str, key:&str, value: serde_json::Value, tags: Vec<String>) -> Result<()> {
        let now = chrono::Utc::now();
        let entry = MemoryEntry{ key:key.to_string(), value, created_at:now, updated_at:now, expires_at: self.default_ttl.map(|t| now+chrono::Duration::seconds(t as i64)), version:1, tags };
        self.backend.set(agent_id, entry).await
    }
    pub async fn get(&self, agent_id:&str, key:&str) -> Result<Option<serde_json::Value>> { Ok(self.backend.get(agent_id,key).await?.map(|e| e.value)) }
    pub async fn delete(&self, agent_id:&str, key:&str) -> Result<bool> { self.backend.delete(agent_id,key).await }
    pub async fn list(&self, agent_id:&str, prefix:&str) -> Result<Vec<MemoryEntry>> { self.backend.list(agent_id,prefix).await }
    pub async fn exists(&self, agent_id:&str, key:&str) -> Result<bool> { self.backend.exists(agent_id,key).await }
    pub async fn clear_agent(&self, agent_id:&str) -> Result<u64> { self.backend.clear_agent(agent_id).await }
    pub async fn cleanup_expired(&self) -> Result<u64> { self.backend.cleanup_expired().await }
}
