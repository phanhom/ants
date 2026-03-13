"""MySQL for traces. Auto-creates database and tables on first connect."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import pymysql
import pymysql.cursors
import pymysql.err

from ants.runtime.runtime_config import load_runtime_config

log = logging.getLogger(__name__)

_connection: pymysql.connections.Connection | None = None
_ready = False

_TABLES: dict[str, str] = {
    "trace_events": """
        CREATE TABLE IF NOT EXISTS trace_events (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            agent_id VARCHAR(128) NOT NULL,
            trace_type VARCHAR(64) NOT NULL,
            ts VARCHAR(64) NOT NULL,
            payload JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_agent_type (agent_id, trace_type),
            INDEX idx_ts (ts)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
}


def _get_mysql_config() -> dict[str, Any]:
    """Build MySQL config from config.json, with env-var overrides."""
    conf = load_runtime_config()
    mysql = conf.get("mysql") or {}
    if not isinstance(mysql, dict):
        mysql = {}
    return {
        "host": os.getenv("MYSQL_HOST") or mysql.get("host") or "mysql",
        "port": int(os.getenv("MYSQL_PORT") or mysql.get("port") or 3306),
        "user": os.getenv("MYSQL_USER") or mysql.get("user") or "ants",
        "password": os.getenv("MYSQL_PASSWORD") or mysql.get("password") or "changeme",
        "database": os.getenv("MYSQL_DATABASE") or mysql.get("database") or "ants",
    }


def _raw_connect(cfg: dict[str, Any], *, use_db: bool = True) -> pymysql.connections.Connection:
    """Low-level connect; raises on failure."""
    kw: dict[str, Any] = {
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "password": cfg["password"],
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }
    if use_db:
        kw["database"] = cfg["database"]
    return pymysql.connect(**kw)


def _ensure_database(cfg: dict[str, Any]) -> None:
    """Create the database if it doesn't exist."""
    conn = _raw_connect(cfg, use_db=False)
    try:
        db = cfg["database"]
        safe_db = "`" + db.replace("`", "``") + "`"
        with conn.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS " + safe_db
                + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        log.info("database '%s' ensured", db)
    finally:
        conn.close()


def _ensure_tables(conn: pymysql.connections.Connection) -> None:
    """Create all required tables."""
    with conn.cursor() as cur:
        for name, ddl in _TABLES.items():
            cur.execute(ddl)
            log.info("table '%s' ensured", name)
    conn.commit()


def init_db() -> None:
    """Connect to MySQL, create database + all tables. Called once at queen startup.
    Retries until MySQL is reachable, then fails hard on schema errors."""
    global _connection, _ready
    cfg = _get_mysql_config()
    log.info("mysql config: host=%s port=%s user=%s db=%s", cfg["host"], cfg["port"], cfg["user"], cfg["database"])

    max_wait, interval = 120, 3
    elapsed = 0
    while elapsed < max_wait:
        try:
            _ensure_database(cfg)
            _connection = _raw_connect(cfg)
            _ensure_tables(_connection)
            _ready = True
            log.info("mysql ready — all tables created")
            return
        except pymysql.err.OperationalError as e:
            code = e.args[0] if e.args else None
            if code in (2003, 2006, 2013):
                log.warning("mysql not reachable (errno %s), retrying in %ds…", code, interval)
                time.sleep(interval)
                elapsed += interval
            else:
                log.error("mysql operational error (errno %s): %s", code, e)
                raise
        except Exception:
            log.exception("unexpected error during mysql init")
            raise

    raise RuntimeError(f"mysql not reachable after {max_wait}s — check host/port/credentials")


def get_connection() -> pymysql.connections.Connection | None:
    """Return the shared connection if init_db() succeeded."""
    if not _ready or _connection is None:
        return None
    try:
        _connection.ping(reconnect=True)
    except Exception:
        log.warning("mysql connection lost, ping failed")
        return None
    return _connection


def write_trace(agent_id: str, trace_type: str, payload: dict[str, Any]) -> bool:
    conn = get_connection()
    if conn is None:
        return False
    ts = datetime.now(timezone.utc).isoformat()
    payload = {**payload, "agent_id": agent_id}
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trace_events (agent_id, trace_type, ts, payload) VALUES (%s, %s, %s, %s)",
                (agent_id, trace_type, ts, json.dumps(payload, ensure_ascii=False)),
            )
        conn.commit()
        return True
    except Exception:
        log.exception("write_trace failed for %s/%s", agent_id, trace_type)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
