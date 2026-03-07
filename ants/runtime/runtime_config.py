"""Load configs/runtime.yaml and expose as env for 蚁后 and workers."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


def get_runtime_config_path() -> Path:
    """Resolve configs/runtime.yaml path."""
    if os.getenv("ANTS_RUNTIME_CONFIG"):
        return Path(os.environ["ANTS_RUNTIME_CONFIG"])
    for base in (Path.cwd(), Path("/app")):
        p = base / "configs" / "runtime.yaml"
        if p.exists():
            return p
    return Path("/app/configs/runtime.yaml")


def _expand_env(value: Any) -> Any:
    """Replace ${VAR} in strings with os.environ.get(VAR, '')."""
    if isinstance(value, str):
        for m in re.finditer(r"\$\{(\w+)\}", value):
            key = m.group(1)
            value = value.replace(m.group(0), os.environ.get(key, ""))
        return value
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_runtime_config() -> dict[str, Any]:
    """Load runtime.yaml and expand ${VAR} placeholders from env."""
    path = get_runtime_config_path()
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _expand_env(raw)


def get_llm_api_key(conf: dict[str, Any] | None = None, token_ref: str | None = None) -> str:
    """
    Resolve LLM API key by optional token_ref. If conf has llm.api_keys and token_ref is set,
    return api_keys[token_ref]; else return llm.api_key (default). Uses expanded values from env.
    """
    if conf is None:
        conf = load_runtime_config()
    llm = conf.get("llm") or {}
    api_keys = llm.get("api_keys")
    if isinstance(api_keys, dict) and token_ref and token_ref in api_keys:
        return str(api_keys.get(token_ref, ""))
    return str(llm.get("api_key", "") or os.getenv("LLM_API_KEY", ""))


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
