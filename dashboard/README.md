# Ants Dashboard

Standalone UI for an Ants colony: topology, per-agent status, instruction submission, and trace event browsing. **Not part of the worker runtime**—it talks to the queen HTTP API and, when configured, reads traces from MySQL via its own backend.

---

## Contents

- [Overview](#overview)
- [Stack](#stack)
- [Development](#development)
- [Docker](#docker)
- [Configuration](#configuration)
- [API (backend)](#api-backend)

---

## Overview

| Capability | Description |
|------------|-------------|
| **Colony view** | Tree of agents and status; links to per-agent detail. |
| **Agent detail** | Single agent status, logs, and context. |
| **Instruction** | Send a user instruction to the queen (same as `POST /instruction`). |
| **Traces** | List recent trace events from MySQL `trace_events` (optional; requires DB). |

The dashboard does not run inside worker containers. It is a separate SPA plus a small Node server that proxies the SPA and exposes `GET /api/traces` when MySQL is configured.

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Vite, React 18, TypeScript, Tailwind CSS |
| Routing | React Router 6 |
| Backend | Node (serve SPA + `/api/traces` → MySQL) |
| Data | Queen: `GET /status`, `POST /instruction`. Traces: MySQL `trace_events`. |

Queen base URL is set at build time via `VITE_QUEEN_URL`; the SPA calls that origin for status and instructions.

---

## Development

**SPA only (no traces)**

```bash
npm install
npm run dev
```

Runs Vite dev server on port 3000. Set `VITE_QUEEN_URL=http://localhost:22000` (e.g. in `.env`) so the app can reach the queen.

**SPA + backend (with traces)**

```bash
npm run dev    # Terminal 1: Vite
npm run server # Terminal 2: SPA + /api/traces (Node)
```

With `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` set, the server will connect to MySQL and serve trace data at `GET /api/traces`.

---

## Docker

The dashboard is built and run from the **repo root** via Compose:

```bash
docker-compose up -d
# Dashboard: http://localhost:21999
```

| Build arg | Default | Purpose |
|-----------|---------|---------|
| `VITE_QUEEN_URL` | `http://localhost:22000` | Queen base URL baked into the SPA. |

Runtime env for the dashboard container: `MYSQL_*` (see [Configuration](#configuration)). Ants itself does not expose a trace API; the dashboard backend connects to the same MySQL used for dual-write (if any).

---

## Configuration

| Variable | Purpose |
|----------|---------|
| `VITE_QUEEN_URL` | Queen base URL (build-time; e.g. `http://queen:22000` in Docker). |
| `MYSQL_HOST` | MySQL host for traces. Omit to disable trace tab. |
| `MYSQL_PORT` | Default `3306`. |
| `MYSQL_USER` | Default `ants`. |
| `MYSQL_PASSWORD` | Required if using traces. |
| `MYSQL_DATABASE` | Default `ants`. |

---

## API (backend)

When the Node server runs and MySQL is configured:

| Endpoint | Description |
|----------|-------------|
| `GET /api/traces` | Recent rows from `trace_events` (e.g. for Traces page). |

All other paths are served as the SPA (index.html and assets). The queen is called directly by the browser using `VITE_QUEEN_URL`.
