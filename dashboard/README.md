# Ants Dashboard

Standalone UI for Ants: colony status, agent detail, send instruction, and trace events. **Not part of worker containers**; only talks to the queen API and (optionally) reads traces from MySQL via its own backend.

- **SPA**: Vite + React 18 + TypeScript + Tailwind. Calls `GET /status`, `POST /instruction` on the queen (base URL from `VITE_QUEEN_URL`).
- **Backend**: Node server serves the SPA and `GET /api/traces` (reads from MySQL `trace_events`). Ants does not expose a trace API; the dashboard backend connects to the same DB.

## Dev

```bash
npm install
npm run dev          # SPA on :3000 (Vite)
# In another terminal, with MySQL env set:
npm run server       # SPA + /api/traces on :3000 (Node)
```

Set `VITE_QUEEN_URL=http://localhost:22000` (or in `.env`) so the SPA can reach the queen.

## Docker

Built and run via repo root:

```bash
docker-compose up -d
# Dashboard: http://localhost:21999
```

Build args: `VITE_QUEEN_URL` (default `http://localhost:22000`). Env for traces: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.
