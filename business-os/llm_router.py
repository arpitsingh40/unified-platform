"""Multi-Provider LLM Router — intelligent model dispatch across providers.

Every agent decision and autonomous execution uses this router.
Supports: DeepSeek, Anthropic, OpenAI, Moonshot (Kimi) simultaneously.
Falls back across providers in priority order. No single point of failure.

Model chains per use case:
  agent_decision:  deepseek-v4-pro → deepseek-v4-flash
  agent_ultra:     deepseek-v4-pro
  agent_fast:      deepseek-v4-flash
  verification:    deepseek-v4-flash

Add API keys in .env to unlock more providers:
  DEEPSEEK_API_KEY (required), ANTHROPIC_API_KEY, OPENAI_API_KEY, MOONSHOT_API_KEY
"""
import os
import json
import time
import logging
from typing import Optional
import requests

log = logging.getLogger("llm_router")

# ── Model chain definitions ──

AGENT_DECISION_CHAIN = [
    "deepseek-v4-pro",
    "deepseek-v4-flash",
]

AGENT_ULTRA_CHAIN = [
    "deepseek-v4-pro",
]

AGENT_FAST_CHAIN = [
    "deepseek-v4-flash",
]

VERIFICATION_CHAIN = [
    "deepseek-v4-flash",
]

# ── Provider registry ──

class _Provider:
    # Set up an OpenAI-compatible provider session
    def __init__(self, name: str, base_url: str, api_key: str, model_prefix: str = ""):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_prefix = model_prefix
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})

    # Normalize the system prompt to plain text
    def _system_text(self, system) -> Optional[str]:
        if not system:
            return None
        if isinstance(system, str):
            return system
        if isinstance(system, list):
            texts = [s["text"] for s in system if isinstance(s, dict) and isinstance(s.get("text"), str) and s["text"].strip()]
            return "\n".join(texts) if texts else None
        return None

    # Call the provider with three retries
    def call(self, model: str, system=None, messages=None, max_tokens=600) -> dict:
        msgs = []
        sys_text = self._system_text(system)
        if sys_text:
            msgs.append({"role": "system", "content": sys_text})
        for m in (messages or []):
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                text_parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
                content = "\n".join(text_parts) if text_parts else str(content)
            msgs.append({"role": role, "content": content})

        body = {"model": model, "messages": msgs, "max_tokens": max_tokens}

        for attempt in range(3):
            resp = None
            try:
                resp = self._session.post(f"{self.base_url}/chat/completions", json=body, timeout=60)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                status = resp.status_code if resp and hasattr(resp, 'status_code') else 0
                if attempt < 2 and status in (429, 503, 502):
                    delay = 2 ** attempt * 2
                    time.sleep(delay)
                    continue
                detail = resp.text[:200] if resp else str(e)[:200]
                raise RuntimeError(f"{self.name} API error ({status}): {detail}")

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {
                "text": text,
                "model": model,
                "provider": self.name,
                "input_tokens": usage.get("prompt_tokens", 0) or 0,
                "output_tokens": usage.get("completion_tokens", 0) or 0,
            }

        raise RuntimeError(f"{self.name}: all retries exhausted")


_providers: list[_Provider] = []
_initialized = False


# Register every configured provider once at startup
def _init_providers():
    global _providers, _initialized
    if _initialized:
        return

    # DeepSeek (primary — required)
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if ds_key:
        _providers.append(_Provider("deepseek", "https://api.deepseek.com/v1", ds_key))

    # Anthropic (via API)
    anthro_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if anthro_key:
        _providers.append(_Provider("anthropic", "https://api.anthropic.com/v1", anthro_key))

    # OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_key:
        _providers.append(_Provider("openai", "https://api.openai.com/v1", openai_key))

    # Moonshot (Kimi K2/K3)
    moonshot_key = os.environ.get("MOONSHOT_API_KEY", "").strip()
    if moonshot_key:
        _providers.append(_Provider("moonshot", "https://api.moonshot.cn/v1", moonshot_key))

    _initialized = True
    names = [p.name for p in _providers]
    log.info(f"LLM Router: {len(_providers)} providers ({', '.join(names)})")


def available_models() -> list[str]:
    """Models available across all connected providers."""
    _init_providers()
    models = []
    for p in _providers:
        if p.name == "deepseek":
            models.extend(["deepseek-v4-pro", "deepseek-v4-flash"])
        elif p.name == "anthropic":
            models.extend(["claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-8"])
        elif p.name == "openai":
            models.extend(["gpt-4o", "gpt-4o-mini"])
        elif p.name == "moonshot":
            models.extend(["moonshot-v1-8k", "kimi-k2"])
    return models


def _model_to_provider(model: str) -> Optional[_Provider]:
    """Route a model name to the correct provider."""
    _init_providers()
    model_lower = model.lower()
    for p in _providers:
        if p.name == "deepseek" and "deepseek" in model_lower:
            return p
        if p.name == "anthropic" and ("claude" in model_lower or "fable" in model_lower):
            return p
        if p.name == "openai" and ("gpt" in model_lower or "o1" in model_lower or "o3" in model_lower):
            return p
        if p.name == "moonshot" and ("moonshot" in model_lower or "kimi" in model_lower):
            return p
    # Fallback: try first available provider
    return _providers[0] if _providers else None


def smart_call(
    model_chain: list[str] = None,
    system=None,
    messages=None,
    max_tokens=600,
    fallback_chain: list[str] = None,
) -> dict:
    """Call LLM with smart fallback across providers.

    Tries each model in model_chain. If that model's provider is unavailable,
    falls through the fallback_chain (provider-agnostic). Returns {text, model, provider, tokens}.
    """
    _init_providers()
    if not _providers:
        raise RuntimeError("No LLM providers configured — set DEEPSEEK_API_KEY in .env")

    chain = model_chain or AGENT_DECISION_CHAIN
    fallback = fallback_chain or ["deepseek-v4-flash"]
    all_models = list(chain) + [m for m in fallback if m not in chain]

    last_err = None
    for model in all_models:
        provider = _model_to_provider(model)
        if not provider:
            log.debug(f"LLM Router: no provider for model {model}, skipping")
            continue
        try:
            result = provider.call(model, system=system, messages=messages, max_tokens=max_tokens)
            log.info(f"LLM Router: {model} via {provider.name} — {result['input_tokens']}+{result['output_tokens']} tokens")
            return result
        except Exception as e:
            log.warning(f"LLM Router: {model} via {provider.name} failed — {str(e)[:100]}")
            last_err = e
            continue

    raise RuntimeError(f"LLM Router: all models exhausted. Last error: {last_err}")


# ── Convenience wrappers ──

def agent_decision(system=None, messages=None, max_tokens=600) -> dict:
    """Agent decision call — tries best models first."""
    return smart_call(
        model_chain=AGENT_DECISION_CHAIN,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
    )


def agent_ultra(system=None, messages=None, max_tokens=2000) -> dict:
    """Agent ultra call — highest quality."""
    return smart_call(
        model_chain=AGENT_ULTRA_CHAIN,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
        fallback_chain=["deepseek-v4-pro"],
    )


def agent_fast(system=None, messages=None, max_tokens=600) -> dict:
    """Agent fast call — cheapest path."""
    return smart_call(
        model_chain=AGENT_FAST_CHAIN,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
    )


def verify_call(system=None, messages=None, max_tokens=300) -> dict:
    """Verification call — cheap, fast."""
    return smart_call(
        model_chain=VERIFICATION_CHAIN,
        system=system,
        messages=messages,
        max_tokens=max_tokens,
    )


# ── Self-check ──
if __name__ == "__main__":
    _init_providers()
    print(f"Providers: {[p.name for p in _providers]}")
    print(f"Models: {available_models()}")
    print(f"Agent chain: {AGENT_DECISION_CHAIN}")
    print(f"Ultra chain: {AGENT_ULTRA_CHAIN}")
    print(f"Fast chain: {AGENT_FAST_CHAIN}")
    print("OK — LLM Router ready")
