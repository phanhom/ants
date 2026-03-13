/**
 * Dashboard backend: serves SPA, trace queries, cost aggregation, reports,
 * tasks grouping, conversations, and MinIO file proxy.
 */
const fs = require("fs");
const path = require("path");
const http = require("http");

const dist = path.join(__dirname, "..", "dist");
const indexHtml = path.join(dist, "index.html");

// ── Optional deps ────────────────────────────────────────────────────────────

let mysql = null;
try { mysql = require("mysql2/promise"); } catch {}

let Minio = null;
try { Minio = require("minio"); } catch {}

// ── MySQL ────────────────────────────────────────────────────────────────────

function getMysqlConfig() {
  const host = process.env.MYSQL_HOST || process.env.MYSQL_HOSTNAME;
  if (!host) return null;
  return {
    host,
    port: parseInt(process.env.MYSQL_PORT || "3306", 10),
    user: process.env.MYSQL_USER || "ants",
    password: process.env.MYSQL_PASSWORD || "",
    database: process.env.MYSQL_DATABASE || "ants",
  };
}

async function queryDb(sql, params) {
  const cfg = getMysqlConfig();
  if (!cfg || !mysql) return null;
  const conn = await mysql.createConnection(cfg);
  try {
    const [rows] = await conn.execute(sql, params);
    return rows;
  } finally {
    await conn.end();
  }
}

function parsePayload(row) {
  return {
    agent_id: row.agent_id,
    trace_type: row.trace_type,
    ts: row.ts,
    payload: typeof row.payload === "string" ? JSON.parse(row.payload || "{}") : row.payload || {},
  };
}

// ── MinIO ────────────────────────────────────────────────────────────────────

const MINIO_BUCKET = process.env.MINIO_BUCKET || "ants";

function getMinioClient() {
  if (!Minio) return null;
  const endpoint = process.env.MINIO_ENDPOINT || process.env.MINIO_HOST;
  if (!endpoint) return null;
  return new Minio.Client({
    endPoint: endpoint,
    port: parseInt(process.env.MINIO_PORT || "9000", 10),
    useSSL: (process.env.MINIO_USE_SSL || "").toLowerCase() === "true",
    accessKey: process.env.MINIO_ACCESS_KEY || process.env.MINIO_ROOT_USER || "ants",
    secretKey: process.env.MINIO_SECRET_KEY || process.env.MINIO_ROOT_PASSWORD || "antspassword",
  });
}

async function ensureBucket(mc) {
  const exists = await mc.bucketExists(MINIO_BUCKET);
  if (!exists) await mc.makeBucket(MINIO_BUCKET);
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function jsonResponse(res, data, status = 200) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(data));
}

function dbUnavailable(res, msg) {
  jsonResponse(res, {
    ok: true,
    events: [], entries: [], reports: [], tasks: [], messages: [],
    db_configured: false,
    message: msg || "MySQL not configured. Set MYSQL_HOST env for the dashboard backend.",
  });
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
      catch { resolve({}); }
    });
    req.on("error", reject);
  });
}

// ── Server ───────────────────────────────────────────────────────────────────

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host}`);
  const pathname = url.pathname;

  // CORS for dev
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") { res.statusCode = 204; res.end(); return; }

  try {
    // ── GET /api/traces ────────────────────────────────────────────────────
    if (pathname === "/api/traces" && req.method === "GET") {
      const cfg = getMysqlConfig();
      if (!cfg || !mysql) return dbUnavailable(res);
      const agentId = url.searchParams.get("agent_id");
      const traceType = url.searchParams.get("trace_type");
      const since = url.searchParams.get("since");
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "100", 10) || 100, 500);
      let sql = "SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE 1=1";
      const params = [];
      if (agentId) { sql += " AND agent_id = ?"; params.push(agentId); }
      if (traceType) { sql += " AND trace_type = ?"; params.push(traceType); }
      if (since) { sql += " AND ts >= ?"; params.push(since); }
      sql += " ORDER BY ts DESC LIMIT ?";
      params.push(limit);
      const rows = await queryDb(sql, params);
      if (rows === null) return dbUnavailable(res);
      return jsonResponse(res, { ok: true, events: rows.map(parsePayload), db_configured: true });
    }

    // ── GET /api/costs ─────────────────────────────────────────────────────
    if (pathname === "/api/costs" && req.method === "GET") {
      const cfg = getMysqlConfig();
      if (!cfg || !mysql) return dbUnavailable(res);
      const agentId = url.searchParams.get("agent_id");
      const since = url.searchParams.get("since");
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "500", 10) || 500, 2000);
      let sql = "SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE trace_type = 'llm_usage'";
      const params = [];
      if (agentId) { sql += " AND agent_id = ?"; params.push(agentId); }
      if (since) { sql += " AND ts >= ?"; params.push(since); }
      sql += " ORDER BY ts DESC LIMIT ?";
      params.push(limit);
      const rows = await queryDb(sql, params);
      if (rows === null) return dbUnavailable(res);
      const entries = rows.map((r) => {
        const p = typeof r.payload === "string" ? JSON.parse(r.payload || "{}") : r.payload || {};
        return {
          ts: r.ts,
          agent_id: r.agent_id,
          model: p.model || "unknown",
          prompt_tokens: p.prompt_tokens || 0,
          completion_tokens: p.completion_tokens || 0,
          total_tokens: p.total_tokens || 0,
          request_duration_ms: p.request_duration_ms || null,
        };
      });
      return jsonResponse(res, { ok: true, entries, db_configured: true });
    }

    // ── GET /api/reports ───────────────────────────────────────────────────
    if (pathname === "/api/reports" && req.method === "GET") {
      const cfg = getMysqlConfig();
      if (!cfg || !mysql) return dbUnavailable(res);
      const agentId = url.searchParams.get("agent_id");
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 500);
      let sql = "SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE trace_type = 'report'";
      const params = [];
      if (agentId) { sql += " AND agent_id = ?"; params.push(agentId); }
      sql += " ORDER BY ts DESC LIMIT ?";
      params.push(limit);
      const rows = await queryDb(sql, params);
      if (rows === null) return dbUnavailable(res);
      const reports = rows.map((r) => {
        const p = typeof r.payload === "string" ? JSON.parse(r.payload || "{}") : r.payload || {};
        return {
          agent_id: r.agent_id,
          ts: r.ts,
          title: p.title || "Untitled",
          body: p.body || "",
          status: p.status || "final",
        };
      });
      return jsonResponse(res, { ok: true, reports, db_configured: true });
    }

    // ── GET /api/tasks ─────────────────────────────────────────────────────
    if (pathname === "/api/tasks" && req.method === "GET") {
      const cfg = getMysqlConfig();
      if (!cfg || !mysql) return dbUnavailable(res);
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "200", 10) || 200, 1000);
      const rows = await queryDb(
        "SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE trace_type IN ('aip', 'todo') ORDER BY ts DESC LIMIT ?",
        [limit],
      );
      if (rows === null) return dbUnavailable(res);
      const events = rows.map(parsePayload);

      // Group by trace_id
      const groups = new Map();
      for (const e of events) {
        const tid = (e.payload?.trace_id) || (e.payload?.correlation_id) || "unknown";
        if (!groups.has(tid)) groups.set(tid, []);
        groups.get(tid).push(e);
      }

      const tasks = [];
      for (const [traceId, evts] of groups) {
        evts.sort((a, b) => a.ts.localeCompare(b.ts));
        const agents = [...new Set(evts.map((e) => e.agent_id))];
        const instruction = evts.find((e) => e.payload?.action === "user_instruction")?.payload?.instruction
          || evts.find((e) => e.payload?.intent)?.payload?.intent
          || "";
        const todos = evts.filter((e) => e.trace_type === "todo");
        const completedTodos = todos.filter((e) => e.payload?.status === "completed").length;
        const totalTodos = todos.length || 1;
        const progress = Math.round((completedTodos / totalTodos) * 100);
        const hasFailed = evts.some((e) => e.payload?.status === "Failed" || e.payload?.error);
        const allDone = todos.length > 0 && completedTodos === todos.length;
        const status = hasFailed ? "failed" : allDone ? "completed" : "working";

        tasks.push({
          trace_id: traceId,
          instruction: typeof instruction === "string" ? instruction : "",
          ts: evts[0]?.ts || "",
          events: evts.slice(0, 50),
          agents,
          status,
          progress,
        });
      }

      tasks.sort((a, b) => b.ts.localeCompare(a.ts));
      return jsonResponse(res, { ok: true, tasks, db_configured: true });
    }

    // ── GET /api/conversations ─────────────────────────────────────────────
    if (pathname === "/api/conversations" && req.method === "GET") {
      const cfg = getMysqlConfig();
      if (!cfg || !mysql) return dbUnavailable(res);
      const agentId = url.searchParams.get("agent_id");
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "100", 10) || 100, 500);
      if (!agentId) return jsonResponse(res, { ok: false, messages: [], message: "agent_id required" }, 400);
      const rows = await queryDb(
        "SELECT agent_id, ts, payload FROM trace_events WHERE trace_type = 'conversation' AND agent_id = ? ORDER BY ts DESC LIMIT ?",
        [agentId, limit],
      );
      if (rows === null) return dbUnavailable(res);
      const messages = rows.map((r) => {
        const p = typeof r.payload === "string" ? JSON.parse(r.payload || "{}") : r.payload || {};
        return { ts: r.ts, agent_id: r.agent_id, role: p.role || "unknown", content: p.content || "" };
      }).reverse();
      return jsonResponse(res, { ok: true, messages, db_configured: true });
    }

    // ── MinIO: GET /api/files ──────────────────────────────────────────────
    if (pathname === "/api/files" && req.method === "GET") {
      const mc = getMinioClient();
      if (!mc) return jsonResponse(res, { ok: true, files: [], prefix: "", configured: false, message: "MinIO not configured. Set MINIO_ENDPOINT env." });
      await ensureBucket(mc);
      const prefix = url.searchParams.get("prefix") || "";
      const delimiter = url.searchParams.get("delimiter") || "/";
      const files = [];
      const stream = mc.listObjectsV2(MINIO_BUCKET, prefix, false);
      await new Promise((resolve, reject) => {
        stream.on("data", (obj) => {
          if (obj.prefix) {
            const name = obj.prefix.replace(prefix, "").replace(/\/$/, "");
            if (name) files.push({ name, key: obj.prefix, size: 0, lastModified: "", isDirectory: true });
          } else {
            const name = (obj.name || "").replace(prefix, "");
            if (name) files.push({
              name,
              key: obj.name,
              size: obj.size || 0,
              lastModified: obj.lastModified ? new Date(obj.lastModified).toISOString() : "",
              isDirectory: false,
            });
          }
        });
        stream.on("end", resolve);
        stream.on("error", reject);
      });
      files.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory) return a.isDirectory ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return jsonResponse(res, { ok: true, files, prefix, configured: true });
    }

    // ── MinIO: GET /api/files/download ─────────────────────────────────────
    if (pathname === "/api/files/download" && req.method === "GET") {
      const mc = getMinioClient();
      if (!mc) return jsonResponse(res, { ok: false, message: "MinIO not configured" }, 503);
      const key = url.searchParams.get("key");
      if (!key) return jsonResponse(res, { ok: false, message: "key required" }, 400);
      await ensureBucket(mc);
      const stat = await mc.statObject(MINIO_BUCKET, key);
      const ext = path.extname(key).toLowerCase();
      const mimeTypes = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
        ".webp": "image/webp", ".svg": "image/svg+xml", ".pdf": "application/pdf",
        ".json": "application/json", ".yaml": "text/yaml", ".yml": "text/yaml",
        ".md": "text/markdown", ".txt": "text/plain", ".csv": "text/csv",
        ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
      };
      res.setHeader("Content-Type", mimeTypes[ext] || "application/octet-stream");
      res.setHeader("Content-Length", stat.size);
      const stream = await mc.getObject(MINIO_BUCKET, key);
      stream.pipe(res);
      return;
    }

    // ── MinIO: POST /api/files/upload ──────────────────────────────────────
    if (pathname === "/api/files/upload" && req.method === "POST") {
      const mc = getMinioClient();
      if (!mc) return jsonResponse(res, { ok: false, message: "MinIO not configured" }, 503);
      await ensureBucket(mc);

      // Simple multipart parsing for single file
      const contentType = req.headers["content-type"] || "";
      if (!contentType.includes("multipart/form-data")) {
        return jsonResponse(res, { ok: false, message: "multipart/form-data required" }, 400);
      }
      const boundary = contentType.split("boundary=")[1];
      if (!boundary) return jsonResponse(res, { ok: false, message: "No boundary" }, 400);

      const chunks = [];
      await new Promise((resolve) => {
        req.on("data", (c) => chunks.push(c));
        req.on("end", resolve);
      });
      const body = Buffer.concat(chunks);
      const bodyStr = body.toString("latin1");
      const parts = bodyStr.split("--" + boundary).filter((p) => p.trim() && p.trim() !== "--");

      let fileBuffer = null;
      let fileName = "upload";
      let prefix = "";

      for (const part of parts) {
        const headerEnd = part.indexOf("\r\n\r\n");
        if (headerEnd === -1) continue;
        const headers = part.slice(0, headerEnd);
        const content = part.slice(headerEnd + 4).replace(/\r\n$/, "");

        if (headers.includes('name="prefix"')) {
          prefix = content.trim();
        } else if (headers.includes('name="file"')) {
          const fnMatch = headers.match(/filename="([^"]+)"/);
          if (fnMatch) fileName = fnMatch[1];
          const contentStart = body.indexOf(Buffer.from("\r\n\r\n", "latin1"), body.indexOf(Buffer.from(headers.slice(0, 40), "latin1"))) + 4;
          const nextBoundary = body.indexOf(Buffer.from("\r\n--" + boundary, "latin1"), contentStart);
          fileBuffer = body.slice(contentStart, nextBoundary);
        }
      }

      if (!fileBuffer) return jsonResponse(res, { ok: false, message: "No file found" }, 400);
      const key = prefix + fileName;
      await mc.putObject(MINIO_BUCKET, key, fileBuffer, fileBuffer.length);
      return jsonResponse(res, { ok: true, key, size: fileBuffer.length });
    }

    // ── MinIO: DELETE /api/files ────────────────────────────────────────────
    if (pathname === "/api/files" && req.method === "DELETE") {
      const mc = getMinioClient();
      if (!mc) return jsonResponse(res, { ok: false, message: "MinIO not configured" }, 503);
      const key = url.searchParams.get("key");
      if (!key) return jsonResponse(res, { ok: false, message: "key required" }, 400);
      await mc.removeObject(MINIO_BUCKET, key);
      return jsonResponse(res, { ok: true });
    }

    // ── SPA: serve dist files ──────────────────────────────────────────────
    let file = pathname === "/" ? "/index.html" : pathname;
    const filePath = path.join(dist, file.replace(/^\//, ""));
    if (!filePath.startsWith(dist)) { res.statusCode = 403; res.end("Forbidden"); return; }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        if (file === "/index.html" || !path.extname(filePath)) {
          fs.readFile(indexHtml, (e2, d2) => {
            if (e2) { res.statusCode = 404; res.end("Not found"); return; }
            res.setHeader("Content-Type", "text/html");
            res.end(d2);
          });
          return;
        }
        res.statusCode = 404;
        res.end("Not found");
        return;
      }
      const ext = path.extname(filePath);
      const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".ico": "image/x-icon", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2" };
      res.setHeader("Content-Type", types[ext] || "application/octet-stream");
      res.end(data);
    });
  } catch (e) {
    console.error("Server error:", e);
    if (!res.headersSent) jsonResponse(res, { ok: false, message: String(e?.message || e) }, 500);
  }
});

const port = parseInt(process.env.PORT || "3000", 10);
server.listen(port, "0.0.0.0", () => {
  console.log(`Dashboard listening on ${port}`);
});
