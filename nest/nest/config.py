"""Platform configuration loader for Nest."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _find_config_path() -> Path:
    env = (os.getenv("NEST_CONFIG") or "").strip()
    if env:
        return Path(env)
    for base in (Path.cwd(), Path("/app")):
        p = base / "configs" / "nest.json"
        if p.exists():
            return p
    return Path("/app/configs/nest.json")


_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    p = _find_config_path()
    if not p.exists():
        _cache = {}
        return _cache
    _cache = json.loads(p.read_text(encoding="utf-8")) or {}
    return _cache


def get_mysql_config() -> dict[str, Any]:
    conf = load_config().get("mysql") or {}
    return {
        "host": os.getenv("MYSQL_HOST") or conf.get("host") or "mysql",
        "port": int(os.getenv("MYSQL_PORT") or conf.get("port") or 3306),
        "user": os.getenv("MYSQL_USER") or conf.get("user") or "ants",
        "password": os.getenv("MYSQL_PASSWORD") or conf.get("password") or "changeme",
        "database": os.getenv("MYSQL_DATABASE") or conf.get("database") or "ants",
    }


def get_registry_config() -> dict[str, Any]:
    return load_config().get("registry") or {}
