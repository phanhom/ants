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
| **AIP** | Ants Interaction Protocol: structured messages, retries, backoff. Send layer keeps only `aip_id`; callers pass `trace_id` / `agent_id` via `log_extra` for observability. |

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

Topology is configuration-driven; no hardcoded roles. Add or remove agents via `configs/agents/*.yaml` and (optionally) `POST /internal/spawn`.

---

## Quick start

**Local (queen only)**

```bash
pip install -e .
uvicorn ants.api.main:app --reload --port 22000
```

**With Docker (queen + workers)**

```bash
docker build -t ants .
docker run -p 22000:22000 \
  -e ANTS_HOST_PROJECT_ROOT="$(pwd)" \
  -e ANTS_IMAGE=ants:latest \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)":/app/host \
  ants
```

Queen will spawn worker containers from config when `ANTS_AUTO_SPAWN_DEFAULT=1` (default).

---

## API surface

| Interface | Path | Purpose |
|-----------|------|---------|
| Status | `GET /status` | Self, subtree, or colony-wide status. Queen: `scope=colony \| self \| subtree`. |
| Instruction | `POST /instruction` | User instruction body → queen decomposes and delegates. |
| AIP | `POST /aip` | Send/receive AIP messages. Queen forwards or, when `to=self` and `action=user_instruction`, decomposes and delegates. |
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

**Compose (queen + workers + optional dashboard)**

From repo root:

```bash
export PWD=$(pwd)
docker-compose up -d
```

| Service   | Port  | Notes |
|-----------|-------|--------|
| Queen     | 22000 | Status, instruction, AIP. |
| Dashboard | 21999 | SPA + backend; optional, needs `MYSQL_*` for traces. |

**Image**

Default base: `python:3.14-slim`. Override in Dockerfile with `ARG PYTHON_VERSION=3.13-slim` if needed.

<details>
<summary>Environment (selection)</summary>

| Variable | Purpose |
|----------|---------|
| `ANTS_CONFIG_DIR` | Agent config directory. |
| `ANTS_AUTO_SPAWN_DEFAULT` | `1` = spawn all workers at startup. |
| `ANTS_HOST_PROJECT_ROOT`, `ANTS_IMAGE` | For spawn volume/image. |
| `AIP_SEND_TIMEOUT`, `AIP_SEND_MAX_RETRIES` | Protocol send tuning. |
| `ANTS_TRACE_LOG`, `ANTS_PROTOCOL_LOG` | Observability. |

Full list: [docs/function.md §12](docs/function.md).
</details>

---

## Documentation

| Doc | Content |
|-----|---------|
| [docs/function.md](docs/function.md) | Design and implementation reference. |
| [docs/aip.md](docs/aip.md) | AIP message and action reference. |
| [docs/shorts.md](docs/shorts.md) | Gaps, backlog, and priorities. |
