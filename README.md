# Ants

**Multi-agent collaboration over AIP.** Each agent runs as a container; the queen decomposes user instructions and dispatches work via the Ants Interaction Protocol. Two surfaces: `POST /aip` and `GET /status`.

---

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [API surface](#api-surface)
- [Observability](#observability)
- [Docker](#docker)
- [Documentation](#documentation)

---

## Overview

| Concept | Description |
|--------|-------------|
| **Queen (蚁后)** | Root container. Receives instructions, decomposes via LLM, and dispatches tasks to workers over AIP. |
| **Workers** | One container per agent in `configs/agents/`. Expose `POST /aip` and `GET /status`. |
| **AIP** | [Agent Interaction Protocol](https://github.com/phanhom/aip): structured messages, retries, backoff. All protocol types come from the `aip-protocol` SDK. |

The system has exactly two external contracts: **container-to-container messaging** (`POST /aip`) and **status** (`GET /status`). The queen also exposes `POST /instruction` as a convenience entry for user instructions.

---

## Architecture

```
                    POST /instruction  or  POST /aip (user_instruction)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Queen (creator_decider)                                                │
│  · Decompose instruction → per-worker tasks                             │
│  · async_send_aip_batch to workers                                      │
│  · GET /status?scope=colony → aggregate                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        ┌──────────┐          ┌──────────┐          ┌──────────┐
        │ Worker A │          │ Worker B │          │ Worker C │
        │ POST /aip│          │ POST /aip│          │ POST /aip│
        │ GET /stat│          │ GET /stat│          │ GET /stat│
        └──────────┘          └──────────┘          └──────────┘
```

Topology is configuration-driven; no hardcoded roles. Add or remove agents via `configs/agents/*.json` and (optionally) `POST /internal/spawn`.

---

## Quick start

**Zero-config Docker Compose** — all inter-service credentials are hardcoded. Just provide your LLM API key:

```bash
# 1. Set your LLM API key in configs/config.json (the "api_key" field under "llm")
# 2. Start everything:
docker compose up -d
```

That's it. MySQL, MinIO, GitLab, Queen, and Dashboard all wire to each other automatically.

**Local (queen only, for development)**

```bash
pip install -e .
uvicorn ants.api.main:app --reload --port 22000
```

The [AIP SDK](https://github.com/phanhom/aip) (`aip-protocol`) is a required dependency — all protocol models, message types, and send functions come from the SDK. No local protocol implementation is kept.

**Configuration**

All configuration lives in JSON files. No `.env` needed.

| File | Purpose |
|------|---------|
| **configs/config.json** | Unified config: llm, mysql, minio, gitlab, ants runtime settings |
| **configs/agents/*.json** | Per-agent topology and capabilities (creator_decider, backend, frontend_uiux, qa, explorer, bizdev) |
| **docker-compose.yml** | Service definitions (queen, dashboard, mysql, minio, gitlab) |

The only value you must fill in: `llm.api_key` in `configs/config.json`. Everything else has working defaults for the Docker Compose stack.

---

## API surface

| Interface | Path | Purpose |
|-----------|------|---------|
| Status | `GET /status` (alias: `GET /v1/status`) | Self, subtree, or colony-wide status. Queen: `scope=colony \| self \| subtree`. |
| Instruction | `POST /instruction` | User instruction body → queen decomposes and delegates. |
| AIP | `POST /aip` (alias: `POST /v1/aip`) | Send/receive AIP messages. Queen forwards or, when `to=self` and `action=user_instruction`, decomposes and delegates. |
| Internal | `GET /internal/configs`, `POST /internal/spawn` | Admin only (`X-Admin-Token`). |

Request target URL is the address; no need to carry host in the body. See [docs/aip.md](docs/aip.md) for message and action types.

---

## Observability

- **Trace logging**  
  Set `ANTS_TRACE_LOG=1` to enable structured events on logger `ants.trace`: `user_instruction`, `delegate`, `assign_task`, `run_task_start`, `run_task_done`, `llm_call`, `tool_call`. Each line includes `trace_id`, `agent_id`, and `ts` (ISO UTC) for Grafana or similar.

- **Protocol layer**  
  Set `AIP_PROTOCOL_LOG=1` (or `ANTS_PROTOCOL_LOG=1`) for send-layer logs. The library only adds `aip_id` to log records; pass `logger=` and `log_extra={"trace_id": ..., "agent_id": ...}` so protocol logs merge into your own logging.

---

## Docker

**Compose (zero-config)**

From repo root:

```bash
docker compose up -d
```

No `.env` file needed. All inter-service connections (MySQL, MinIO, GitLab) use hardcoded credentials within the Docker network. Only `llm.api_key` in `configs/config.json` is user-supplied.

| Service   | Port  | Notes |
|-----------|-------|--------|
| Queen     | 22000 | Status, instruction, AIP. |
| Dashboard | 22002 | SPA + backend (costs, reports, tasks, traces, artifacts). |
| MinIO API | 22003 | S3-compatible object storage for artifacts. |
| MinIO Console | 22004 | MinIO web console. |
| MySQL     | 22005 | Trace storage. |
| GitLab    | 22006 | Private GitLab for agent tools. |

**Hardcoded service credentials** (same in `docker-compose.yml` and `configs/config.json`):

| Service | User | Password |
|---------|------|----------|
| MySQL | `ants` | `changeme` |
| MinIO | `ants` | `antspassword` |
| GitLab root | `root` | `changeme` |

**Data directory layout** (all under `./data/`, gitignored):

```
data/
├── volumes/           # Per-agent traces, logs, workspace
│   ├── creator_decider/
│   │   ├── workspace/
│   │   ├── logs/
│   │   ├── conversations/
│   │   ├── aip/
│   │   ├── todos/
│   │   ├── reports/
│   │   └── context/
│   ├── backend/
│   └── ...
├── mysql/             # MySQL data files
├── minio/             # MinIO object storage (artifacts)
└── gitlab/            # GitLab
    ├── config/
    ├── data/
    └── logs/
```

All service data lives under `./data/` with bind mounts (no Docker named volumes). Data is portable — just copy or backup the `data/` directory. Wiping `data/` gives a clean slate.

**Image**

Default base: `python:3.14-slim`. Override in Dockerfile with `ARG PYTHON_VERSION=3.13-slim` if needed.

<details>
<summary>Environment variables (selection)</summary>

| Variable | Purpose |
|----------|---------|
| `ANTS_CONFIG_DIR` | Agent config directory (default: `configs/agents`). |
| `ANTS_AUTO_SPAWN_DEFAULT` | `1` = spawn all workers at startup. |
| `ANTS_HOST_PROJECT_ROOT`, `ANTS_IMAGE` | For spawn volume/image. |
| `ANTS_TRACE_LOG`, `ANTS_PROTOCOL_LOG` | Observability toggles. |

Full list: [docs/function.md §12](docs/function.md).
</details>

---

## Documentation

| Doc | Content |
|-----|---------|
| [docs/function.md](docs/function.md) | Design and implementation reference. |
| [docs/aip.md](docs/aip.md) | AIP message and action reference. |
| [docs/shorts.md](docs/shorts.md) | Gaps, backlog, and priorities. |
