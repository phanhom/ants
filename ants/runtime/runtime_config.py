"""Load configs/config.yaml (fallback runtime.yaml) and expose as env for 蚁后 and workers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def get_runtime_config_path() -> Path:
    """Resolve config path: ANTS_RUNTIME_CONFIG or configs/config.yaml."""
    if os.getenv("ANTS_RUNTIME_CONFIG"):
        return Path(os.environ["ANTS_RUNTIME_CONFIG"])
    for base in (Path.cwd(), Path("/app")):
        p = base / "configs" / "config.yaml"
        if p.exists():
            return p
    return Path("/app/configs/config.yaml")


def load_runtime_config() -> dict[str, Any]:
    """Load config.yaml; no env substitution, literal values only."""
    path = get_runtime_config_path()
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def get_ants_config() -> dict[str, Any]:
    """Return expanded 'ants' section from config (for config_dir, spawn, cache, etc.)."""
    conf = load_runtime_config()
    return conf.get("ants") or {}


def get_llm_api_key(conf: dict[str, Any] | None = None, token_ref: str | None = None) -> str:
    """
    Resolve LLM API key by optional token_ref. If conf has llm.api_keys and token_ref is set,
    return api_keys[token_ref]; else return llm.api_key (default).
    """
    if conf is None:
        conf = load_runtime_config()
    llm = conf.get("llm") or {}
    api_keys = llm.get("api_keys")
    if isinstance(api_keys, dict) and token_ref and token_ref in api_keys:
        return str(api_keys.get(token_ref, ""))
    return str(llm.get("api_key", ""))


def runtime_config_to_env(conf: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested runtime config into env vars (e.g. llm.base_url -> LLM_BASE_URL)."""
    out: dict[str, str] = {}
    for key, value in conf.items():
        name = f"{prefix}{key.upper()}" if prefix else key.upper()
        if isinstance(value, dict):
            out.update(runtime_config_to_env(value, prefix=f"{name}_"))
        elif value is not None and not isinstance(value, (dict, list)):
            out[name] = str(value)
    return out
