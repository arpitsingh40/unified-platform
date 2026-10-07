//! JWT auth (HS256) + Axum extractor. Enterprise-grade: org-scoped, role-aware.

use anyhow::{Context, Result};
use axum::{extract::FromRequestParts, http::{request::Parts, StatusCode}, response::{IntoResponse, Response}, Json};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    pub jwt_secret: String,
    pub jwt_issuer: String,
    pub jwt_audience: Option<String>,
}

impl AuthConfig {
    pub fn from_env() -> Self {
        Self {
            jwt_secret: std::env::var("ARI_JWT_SECRET").unwrap_or_else(|_| "dev-only-change-me-in-prod-32chars!".to_string()),
            jwt_issuer: std::env::var("ARI_JWT_ISSUER").unwrap_or_else(|_| "ari".to_string()),
            jwt_audience: std::env::var("ARI_JWT_AUDIENCE").ok(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,    // user_id
    pub org_id: String,
    pub role: String,   // owner | admin | member | viewer
    pub exp: usize,
    pub iat: usize,
    #[serde(default)]
    pub iss: Option<String>,
    #[serde(default)]
    pub aud: Option<String>,
}

#[derive(Debug, Clone)]
pub struct AuthenticatedUser {
    pub user_id: String,
    pub org_id: String,
    pub role: String,
    pub claims: Claims,
}

impl AuthenticatedUser {
    pub fn is_admin(&self) -> bool { matches!(self.role.as_str(), "owner" | "admin") }
    pub fn can_write(&self) -> bool { !matches!(self.role.as_str(), "viewer") }
}

pub fn create_token(cfg: &AuthConfig, user_id: &str, org_id: &str, role: &str, ttl_hours: u64) -> Result<String> {
    use jsonwebtoken::{encode, EncodingKey, Header};
    let now = chrono::Utc::now().timestamp() as usize;
    let exp = (chrono::Utc::now() + chrono::Duration::hours(ttl_hours as i64)).timestamp() as usize;
    let claims = Claims {
        sub: user_id.to_string(),
        org_id: org_id.to_string(),
        role: role.to_string(),
        exp, iat: now,
        iss: Some(cfg.jwt_issuer.clone()),
        aud: cfg.jwt_audience.clone(),
    };
    encode(&Header::default(), &claims, &EncodingKey::from_secret(cfg.jwt_secret.as_bytes())).context("jwt encode")
}

pub fn verify_token(cfg: &AuthConfig, token: &str) -> Result<Claims> {
    use jsonwebtoken::{decode, DecodingKey, Validation, Algorithm};
    let mut v = Validation::new(Algorithm::HS256);
    v.set_issuer(&[cfg.jwt_issuer.clone()]);
    if let Some(aud) = &cfg.jwt_audience { v.set_audience(&[aud.clone()]); }
    let data = decode::<Claims>(token, &DecodingKey::from_secret(cfg.jwt_secret.as_bytes()), &v).context("jwt decode")?;
    Ok(data.claims)
}

// Shared state to extract AuthConfig in extractor. We store it as axum Extension.
#[derive(Clone)]
pub struct AuthState(pub AuthConfig);

#[async_trait::async_trait]
impl<S> FromRequestParts<S> for AuthenticatedUser
where
    S: Send + Sync,
{
    type Rejection = Response;

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        // Try Extension<AuthState> first, fallback to env config
        let cfg = parts.extensions.get::<AuthState>().map(|s| s.0.clone()).unwrap_or_else(AuthConfig::from_env);

        let auth = parts.headers.get(axum::http::header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok())
            .ok_or_else(|| (StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error":"missing Authorization"}))).into_response())?;

        let token = auth.strip_prefix("Bearer ").unwrap_or(auth).trim();
        if token.is_empty() {
            return Err((StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error":"empty token"}))).into_response());
        }
        let claims = verify_token(&cfg, token).map_err(|e| {
            (StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error": format!("invalid token: {}", e)}))).into_response()
        })?;
        // exp check is done by jsonwebtoken Validation; double-check still
        let now = chrono::Utc::now().timestamp() as usize;
        if claims.exp < now {
            return Err((StatusCode::UNAUTHORIZED, Json(serde_json::json!({"error":"token expired"}))).into_response());
        }
        Ok(AuthenticatedUser { user_id: claims.sub.clone(), org_id: claims.org_id.clone(), role: claims.role.clone(), claims })
    }
}
