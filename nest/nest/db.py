"""MySQL for traces. Auto-creates database and tables on first connect."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import pymysql
import pymysql.cursors
import pymysql.err

from nest.config import get_mysql_config

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


def _raw_connect(cfg: dict[str, Any], *, use_db: bool = True) -> pymysql.connections.Connection:
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
    with conn.cursor() as cur:
        for name, ddl in _TABLES.items():
            cur.execute(ddl)
            log.info("table '%s' ensured", name)
    conn.commit()


def init_db() -> None:
    global _connection, _ready
    cfg = get_mysql_config()
    log.info("mysql config: host=%s port=%s db=%s", cfg["host"], cfg["port"], cfg["database"])
    max_wait, interval = 120, 3
    elapsed = 0
    while elapsed < max_wait:
        try:
            _ensure_database(cfg)
            _connection = _raw_connect(cfg)
            _ensure_tables(_connection)
            _ready = True
            log.info("mysql ready")
            return
        except pymysql.err.OperationalError as e:
            code = e.args[0] if e.args else None
            if code in (2003, 2006, 2013):
                log.warning("mysql not reachable (errno %s), retrying in %ds…", code, interval)
                time.sleep(interval)
                elapsed += interval
            else:
                raise
        except Exception:
            log.exception("unexpected error during mysql init")
            raise
    raise RuntimeError(f"mysql not reachable after {max_wait}s")


def get_connection() -> pymysql.connections.Connection | None:
    if not _ready or _connection is None:
        return None
    try:
        _connection.ping(reconnect=True)
    except Exception:
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


def query_traces(
    agent_id: str | None = None,
    trace_type: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conn = get_connection()
    if conn is None:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if agent_id:
        clauses.append("agent_id = %s")
        params.append(agent_id)
    if trace_type:
        clauses.append("trace_type = %s")
        params.append(trace_type)
    if since:
        clauses.append("ts >= %s")
        params.append(since)
    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE {where} ORDER BY id DESC LIMIT %s"
    params.append(limit)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        out = []
        for r in rows:
            p = r.get("payload")
            if isinstance(p, str):
                try:
                    p = json.loads(p)
                except Exception:
                    pass
            out.append({
                "agent_id": r["agent_id"],
                "trace_type": r["trace_type"],
                "ts": r["ts"],
                "payload": p,
            })
        return out
    except Exception:
        log.exception("query_traces failed")
        return []
