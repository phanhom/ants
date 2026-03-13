# TheHive / Ants

**Nest + Ants** — a two-part multi-agent system built on the [AIP protocol](https://github.com/phanhom/aip).

- **Nest** is the management platform (the company). It provides infrastructure (MySQL, MinIO, GitLab), an agent registry with heartbeat-based lifecycle, AIP message routing, trace/cost observability, and a dashboard.
- **Ants** is the talent market (the talent agency). It creates agent teams as Docker containers, equips them with tools and skills, and registers them with a Nest instance.

The two are completely independent. Nest does not know how agents are created — it only sees agents that register via AIP. Ants does not manage infrastructure — it only knows the Nest URL.

---

## Architecture

```
                         ┌─────────────────────────────────────────┐
                         │  Nest (Management Platform)  :22000     │
                         │  ┌────────────┐  ┌──────────────────┐  │
    User / Browser ─────>│  │  Registry   │  │  AIP Router      │  │
                         │  │  Heartbeat  │  │  Trace Storage   │  │
                         │  └────────────┘  └──────────────────┘  │
                         │       ▲    ▲           ▲                │
                         │  Dashboard :22002   MySQL / MinIO       │
                         └───────┼────┼───────────┼────────────────┘
                                 │    │           │
              ┌──────────────────┼────┼───────────┼──────────────┐
              │  Ants (Talent Market)  │           │              │
              │                        │           │              │
              │  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
              │  │ Queen    │  │ Backend  │  │ Explorer │  ...   │
              │  │ :22100   │  │ :22101   │  │ :22101   │       │
              │  └──────────┘  └──────────┘  └──────────┘       │
              │       │ register + heartbeat ──────────>  Nest   │
              └──────────────────────────────────────────────────┘
                               │
                       Remote agents can also
                       register with Nest directly
```

All communication flows through the [AIP protocol](https://github.com/phanhom/aip) (`aip-protocol` SDK v1.3.0).

---

## Quick Start

### Option 1: Full Docker Compose

```bash
# 1. Set your LLM API key
#    Edit ants/configs/config.json → llm.api_key

# 2. Start everything
docker compose up -d

# 3. Open dashboard
open http://localhost:22002
```

### Option 2: Dev mode (fast dashboard iteration)

```bash
./start.sh          # Default: dev mode
./start.sh docker   # Full Docker
./start.sh stop     # Stop everything
```

Dev mode runs Nest, Queen, MySQL, and MinIO in Docker, but serves the dashboard locally with Vite HMR on the same port (`:22002`).

---

## Directory Structure

```
repo/
├── nest/                    # Management Platform
│   ├── nest/                # Python package (api.py, registry.py, db.py, config.py)
│   ├── dashboard/           # React SPA + Node.js backend
│   ├── configs/nest.json    # Platform config (MySQL, MinIO, GitLab, registry)
│   ├── Dockerfile
│   └── pyproject.toml
│
├── ants/                    # Talent Market
│   ├── ants/                # Python package
│   │   ├── agents/          # Worker code (bootstrap, server, runner)
│   │   ├── queen/           # Queen agent (decompose + delegate)
│   │   └── runtime/         # Docker manager, config, traces, models
│   ├── configs/
│   │   ├── config.json      # LLM, Nest URL, spawn settings
│   │   └── agents/          # Per-agent JSON configs
│   ├── shared/tools/        # Hot-loaded Python tools (18 tools)
│   ├── Dockerfile
│   └── pyproject.toml
│
├── data/                    # Persistent storage (gitignored)
├── docker-compose.yml
└── start.sh
```

---

## Services & Ports

| Service | Port | Description |
|---------|------|-------------|
| Nest API | 22000 | Agent registry, AIP routing, traces, status |
| Dashboard | 22002 | SPA + backend (costs, reports, tasks, artifacts) |
| MinIO API | 22003 | S3-compatible object storage |
| MinIO Console | 22004 | MinIO web UI |
| MySQL | 22005 | Trace/cost storage |
| GitLab | 22006 | Private GitLab (profile: full) |
| Queen | 22100 | creator_decider agent |
| Workers | 22101 | Spawned dynamically by Queen |

---

## Nest API (AIP-standard)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/registry/agents` | POST | Agent registration (returns heartbeat_url) |
| `/v1/registry/agents/{id}/heartbeat` | POST | Receive heartbeat |
| `/v1/registry/agents/{id}` | DELETE | Deregistration |
| `/v1/agents` | GET | List all registered agents |
| `/v1/agents/{id}/status` | GET | Single agent status |
| `/v1/status` | GET | Group status (heartbeat-based) |
| `/v1/aip` | POST | Route AIP message by `to` field |
| `/v1/agents/{id}/aip` | POST | Send to specific agent |
| `/v1/traces` | POST | Receive trace events |
| `/v1/traces` | GET | Query traces |
| `/v1/usage` | GET | Cost/usage summary |
| `/instruction` | POST | Convenience: user instruction to root agent |
| `/health` | GET | Health check |

---

## Agent Registration Flow

1. Ants spawner creates a worker container with `NEST_URL=http://nest:22000`
2. Worker starts, calls `POST {NEST_URL}/v1/registry/agents` with its identity
3. Nest returns `{heartbeat_url}` — worker starts a heartbeat loop (every 10s)
4. Nest marks agents `degraded` after 30s without heartbeat, `failed` after 120s
5. On shutdown: `DELETE {NEST_URL}/v1/registry/agents/{id}`

Remote agents (non-Ants) can register the same way. Nest also supports manual agent connection via the dashboard.

---

## Configuration

### Nest (`nest/configs/nest.json`)

Platform infrastructure — MySQL, MinIO, GitLab, registry settings.

### Ants (`ants/configs/config.json`)

LLM settings, Nest URL, spawn settings. The only value you must fill in: `llm.api_key`.

### Agent configs (`ants/configs/agents/*.json`)

Per-agent topology and capabilities. Six default agents: `creator_decider` (queen), `backend`, `frontend_uiux`, `qa`, `explorer`, `bizdev`.

---

## Observability

- **Trace logging**: Set `ANTS_TRACE_LOG=1` for structured events on logger `ants.trace`
- **Protocol logging**: Set `AIP_LOG=1` for AIP send-layer logs
- **Traces**: All agent traces are posted to Nest's `/v1/traces` and stored in MySQL
- **Dashboard**: Real-time view of agents, costs, tasks, conversations, reports, and artifacts

---

## Documentation

| Doc | Content |
|-----|---------|
| [docs/architecture.md](docs/architecture.md) | System architecture and design decisions |
| [docs/aip.md](docs/aip.md) | AIP message and action reference |
| [docs/api.md](docs/api.md) | Complete API reference for Nest and Ants |

---

## Tech Stack

- **Protocol**: [AIP](https://github.com/phanhom/aip) v1.3.0 — agent registration, heartbeat, messaging, observability
- **Backend**: Python 3.13, FastAPI, Pydantic, httpx, Docker SDK
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, recharts, i18next
- **Infrastructure**: MySQL 8.0, MinIO, GitLab CE (optional)
- **Containerization**: Docker Compose, multi-stage builds
