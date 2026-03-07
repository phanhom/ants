/**
 * Dashboard backend: serves SPA and GET /api/traces (reads from MySQL).
 * Ants stays pure; trace data is read here from the same DB ants writes to.
 */
const fs = require("fs");
const path = require("path");
const http = require("http");

const dist = path.join(__dirname, "..", "dist");
const indexHtml = path.join(dist, "index.html");

let mysql = null;
try {
  mysql = require("mysql2/promise");
} catch {
  // mysql2 optional for dev without DB
}

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

async function readTraces(agentId, traceType, limit, since) {
  const cfg = getMysqlConfig();
  if (!cfg || !mysql) return [];
  const conn = await mysql.createConnection(cfg);
  try {
    let sql = "SELECT agent_id, trace_type, ts, payload FROM trace_events WHERE 1=1";
    const params = [];
    if (agentId) {
      sql += " AND agent_id = ?";
      params.push(agentId);
    }
    if (traceType) {
      sql += " AND trace_type = ?";
      params.push(traceType);
    }
    if (since) {
      sql += " AND ts >= ?";
      params.push(since);
    }
    sql += " ORDER BY ts DESC LIMIT ?";
    params.push(Math.min(parseInt(limit, 10) || 100, 500));
    const [rows] = await conn.execute(sql, params);
    return rows.map((r) => ({
      agent_id: r.agent_id,
      trace_type: r.trace_type,
      ts: r.ts,
      payload: typeof r.payload === "string" ? JSON.parse(r.payload || "{}") : r.payload || {},
    }));
  } finally {
    await conn.end();
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host}`);
  if (url.pathname === "/api/traces" && req.method === "GET") {
    const agentId = url.searchParams.get("agent_id") || undefined;
    const traceType = url.searchParams.get("trace_type") || undefined;
    const limit = url.searchParams.get("limit") || "100";
    const since = url.searchParams.get("since") || undefined;
    try {
      const events = await readTraces(agentId, traceType, limit, since);
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ ok: true, events }));
    } catch (e) {
      res.statusCode = 500;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ ok: false, error: String(e.message) }));
    }
    return;
  }

  // SPA: serve dist files
  let file = url.pathname === "/" ? "/index.html" : url.pathname;
  const filePath = path.join(dist, file.replace(/^\//, ""));
  if (!filePath.startsWith(dist)) {
    res.statusCode = 403;
    res.end("Forbidden");
    return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (file === "/index.html" || !path.extname(filePath)) {
        fs.readFile(indexHtml, (e2, d2) => {
          if (e2) {
            res.statusCode = 404;
            res.end("Not found");
            return;
          }
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
    const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".ico": "image/x-icon" };
    res.setHeader("Content-Type", types[ext] || "application/octet-stream");
    res.end(data);
  });
});

const port = parseInt(process.env.PORT || "3000", 10);
server.listen(port, "0.0.0.0", () => {
  console.log(`Dashboard listening on ${port}`);
});
