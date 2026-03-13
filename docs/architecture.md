# Architecture

Nest + Ants: a two-part multi-agent system built on the [AIP protocol](https://github.com/phanhom/aip).

---

## Design Philosophy

The system is split into two independent services with distinct responsibilities:

| Service | Role | Analogy |
|---------|------|---------|
| **Nest** | Agent management platform — provides infrastructure, observability, and routing | The company |
| **Ants** | Agent creator and talent market — creates teams, provides tools and skills | The talent agency |

Nest does not create agents. Ants does not manage infrastructure. The two communicate exclusively via AIP.

---

## System Architecture

```
                         ┌─────────────────────────────────────────┐
                         │  Nest (Management Platform)  :22000     │
                         │  ┌────────────┐  ┌──────────────────┐  │
    User / Dashboard ───>│  │  Registry   │  │  AIP Router      │  │
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
```

---

## Nest — Management Platform

### Responsibilities

- **Agent Registry**: In-memory store of registered agents with heartbeat tracking
- **AIP Router**: Routes AIP messages to agents by `to` field
- **Trace Storage**: Receives and persists trace events to MySQL
- **Status**: Heartbeat-based lifecycle (running → degraded → failed)
- **Dashboard**: React SPA for human observation of the entire system
- **Infrastructure**: MySQL, MinIO, GitLab (all zero-config within Docker)

### Agent Lifecycle

Nest derives agent lifecycle from heartbeat freshness:

| State | Condition |
|-------|-----------|
| `running` | Heartbeat received within `heartbeat_timeout` (30s) |
| `degraded` | No heartbeat for > `heartbeat_timeout` but < `heartbeat_dead` |
| `failed` | No heartbeat for > `heartbeat_dead` (120s) |

### Key Modules

| Module | Purpose |
|--------|---------|
| `nest.api` | FastAPI application — all Nest endpoints |
| `nest.registry` | Thread-safe `AgentRegistry` — register, heartbeat, status building |
| `nest.db` | MySQL connection, auto-create database/tables, trace persistence |
| `nest.config` | Load `nest.json` config, merge with environment variables |

### Configuration (`nest/configs/nest.json`)

```json
{
  "mysql": { "host": "mysql", "port": 3306, "user": "ants", "password": "changeme", "database": "ants" },
  "minio": { "endpoint": "minio", "port": 9000, "access_key": "ants", "secret_key": "antspassword" },
  "gitlab": { "url": "", "token": "" },
  "registry": { "heartbeat_timeout": 30, "heartbeat_dead": 120 }
}
```

All values can be overridden by environment variables (`MYSQL_HOST`, `MYSQL_PORT`, etc.).

---

## Ants — Talent Market

### Responsibilities

- **Create agent teams**: Queen spawns worker containers via Docker SDK
- **Task decomposition**: LLM-based instruction splitting into per-worker tasks
- **Task delegation**: AIP batch send to workers
- **Tools and skills**: Hot-loaded from `/shared/tools`, skills defined per-agent
- **Nest registration**: All agents register with Nest and send heartbeats

### Agent Hierarchy

- **Queen (`creator_decider`)**: Root agent. Receives user instructions, decomposes via LLM, delegates to workers.
- **Workers**: One container per agent in `configs/agents/`. Expose `POST /aip` and `GET /status`.
- **Explorer**: Special worker that only distributes tasks — creates, reports, and dispatches; does not perform work.

Topology is configuration-driven. Add or remove agents via `ants/configs/agents/*.json`.

### Key Modules

| Module | Purpose |
|--------|---------|
| `ants.queen.api` | Queen FastAPI — AIP receive, instruction handling, Nest registration |
| `ants.queen.decompose` | LLM-based task decomposition |
| `ants.agents.server` | Worker FastAPI — AIP receive, status |
| `ants.agents.bootstrap` | Tool hot-loading, Nest registration, heartbeat loop |
| `ants.agents.runner` | LLM conversation loop, tool execution, context management |
| `ants.runtime.docker_manager` | `DockerSpawner` — creates worker containers |
| `ants.runtime.config` | Load agent configs from JSON files |
| `ants.runtime.models` | `AgentConfig`, `PromptProfile`, `EnvironmentPolicy` |
| `ants.runtime.traces` | File-based trace writing (JSONL) |
| `ants.runtime.db` | Posts trace events to Nest's `/v1/traces` (not direct MySQL) |

### Configuration (`ants/configs/config.json`)

```json
{
  "llm": {
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-4",
    "api_key": "",
    "context_length": 128000,
    "max_tokens": 4096
  },
  "nest": { "url": "http://nest:22000", "secret": "" },
  "ants": {
    "auto_spawn": true,
    "image": "ants:latest",
    "network": "ants_default",
    "decompose_llm_timeout": 60,
    "aip_send_timeout": 30,
    "aip_send_max_retries": 4
  }
}
```

The only value you must fill in: `llm.api_key`.

### Agent Configs (`ants/configs/agents/*.json`)

Each file defines one agent:

| Field | Description |
|-------|-------------|
| `agent_id` | Unique identifier |
| `display_name` | Human-readable name |
| `role` | Functional role |
| `superior` | Parent agent ID |
| `subordinates` | Child agent IDs |
| `authority_weight` | Organizational weight (0–100) |
| `skills` | Abstract capabilities |
| `tools_allowed` | Whitelisted tool names |
| `prompt_profile` | Persona for LLM conversations |
| `can_spawn_subordinates` | Whether this agent can spawn children |
| `environment_policy` | Production access rules |

Default agents: `creator_decider`, `backend`, `frontend_uiux`, `qa`, `explorer`, `bizdev`.

---

## Communication Flow

### Registration

1. Queen starts → registers with Nest (`POST /v1/registry/agents`)
2. Queen spawns workers → each worker registers with Nest
3. All agents start heartbeat loops (every 10s → Nest)
4. Nest tracks lifecycle based on heartbeat freshness

### Instruction Processing

1. User sends `POST /instruction` to Nest
2. Nest wraps as AIP `user_instruction` and routes to root agent (Queen)
3. Queen decomposes instruction via LLM into per-worker tasks
4. Queen sends `assign_task` AIP messages to workers via batch
5. Workers execute tasks, log traces, send heartbeats

### Trace Flow

1. Workers post trace events to Nest (`POST /v1/traces`)
2. Nest persists to MySQL (`trace_events` table)
3. Dashboard reads from Nest API (`GET /v1/traces`, `GET /v1/usage`)

---

## Data Storage

### MySQL (`trace_events`)

Auto-created by Nest on startup. Schema:

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT AUTO_INCREMENT | Primary key |
| `agent_id` | VARCHAR(128) | Agent identifier |
| `trace_type` | VARCHAR(64) | Event type (registry, aip, llm_usage, etc.) |
| `ts` | VARCHAR(64) | ISO UTC timestamp |
| `payload` | JSON | Structured event data |

### File Volumes

Each agent has a dedicated directory under `data/volumes/<agent_id>/`:

```
workspace/        Working directory for code and files
logs/             Runtime logs (JSONL)
conversations/    LLM conversation history
aip/              AIP message log
todos/            Task items
reports/          Generated reports
context/          Skill snapshots, context files
```

### MinIO

S3-compatible object storage for artifacts. Accessible at `:22003` (API) and `:22004` (console).

---

## Docker Architecture

### Compose Services

| Service | Container | Image | Port |
|---------|-----------|-------|------|
| Nest | `nest` | Built from `./nest` | 22000 |
| Dashboard | `ants-dashboard` | Built from `./nest/dashboard` | 22002 |
| Queen | `ants-queen` | Built from `./ants` | 22100 |
| MySQL | `ants-mysql` | `mysql:8.0` | 22005 |
| MinIO | `ants-minio` | `minio/minio` | 22003, 22004 |
| GitLab | `ants-gitlab` | `gitlab/gitlab-ce` | 22006 (profile: full) |

Workers are spawned dynamically by the Queen via Docker SDK (Docker-outside-of-Docker pattern). Only the Queen mounts `/var/run/docker.sock`.

### Credentials (zero-config, hardcoded)

| Service | User | Password |
|---------|------|----------|
| MySQL | `ants` | `changeme` |
| MinIO | `ants` | `antspassword` |
| GitLab | `root` | `changeme` |

---

## Environment Variables

| Variable | Service | Description |
|----------|---------|-------------|
| `NEST_URL` | Ants | Nest platform URL |
| `NEST_SECRET` | Ants | Optional auth token for Nest |
| `NEST_CONFIG` | Nest | Path to nest.json |
| `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE` | Nest | MySQL connection (overrides nest.json) |
| `ANTS_HOST_PROJECT_ROOT` | Queen | Host path for volume mounts |
| `ANTS_IMAGE` | Queen | Docker image for workers |
| `ANTS_NETWORK` | Queen | Docker network name |
| `ANTS_CONFIG_DIR` | Queen/Workers | Agent config directory |
| `ANTS_RUNTIME_CONFIG` | Queen | Path to config.json |
| `ANTS_TRACE_LOG` | All agents | Enable structured trace logging |
| `AIP_LOG` | All agents | Enable AIP protocol logging |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Protocol | [AIP](https://github.com/phanhom/aip) v1.3.0 |
| Backend | Python 3.13, FastAPI, Pydantic, httpx, Docker SDK |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui |
| Database | MySQL 8.0 (traces), MinIO (artifacts) |
| Containerization | Docker Compose |
