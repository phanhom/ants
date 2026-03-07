"""Optional MySQL dual-write for traces. If DB is not configured or unavailable, writes are skipped."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ants.runtime.runtime_config import load_runtime_config

_connection = None


def _get_mysql_config() -> dict[str, Any] | None:
    conf = load_runtime_config()
    mysql = conf.get("mysql") or {}
    if not isinstance(mysql, dict):
        return None
    host = mysql.get("host")
    if not host:
        return None
    return {
        "host": host,
        "port": int(mysql.get("port", 3306)),
        "user": mysql.get("user", "ants"),
        "password": mysql.get("password", ""),
        "database": mysql.get("database", "ants"),
    }


def _connect():
    global _connection
    if _connection is not None:
        return _connection
    cfg = _get_mysql_config()
    if not cfg:
        return None
    try:
        import pymysql
        _connection = pymysql.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        _ensure_table(_connection)
        return _connection
    except Exception:
        _connection = None
        return None


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trace_events (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                agent_id VARCHAR(128) NOT NULL,
                trace_type VARCHAR(64) NOT NULL,
                ts VARCHAR(64) NOT NULL,
                payload JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_agent_type (agent_id, trace_type),
                INDEX idx_ts (ts)
            )
        """)
    conn.commit()


def write_trace(agent_id: str, trace_type: str, payload: dict[str, Any]) -> bool:
    """Write one trace event to MySQL. Returns True if written, False if skipped or failed."""
    conn = _connect()
    if conn is None:
        return False
    ts = datetime.now(timezone.utc).isoformat()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trace_events (agent_id, trace_type, ts, payload) VALUES (%s, %s, %s, %s)",
                (agent_id, trace_type, ts, json.dumps(payload, ensure_ascii=False)),
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
