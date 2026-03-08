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

**Configuration** — **configs/config.yaml** 为字面默认值，不读环境变量。可配置：llm（含 context_length、max_tokens）、gitlab、mysql、ants（auto_spawn_default、admin_token、超时等）。工人访问蚁后的地址由代码固定为 `http://host.docker.internal:22000`。

**配置文件一览**

| 文件 | 用途 |
|------|------|
| **configs/config.yaml** | 统一配置：llm、gitlab、mysql、queen、ants（仅业务相关项） |
| **configs/agents/*.yaml** | 各 Agent 拓扑与能力（creator_decider、backend、frontend_uiux、qa、explorer、bizdev） |
| **docker-compose.yml** | 服务定义（queen、dashboard、mysql、gitlab） |

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
| MySQL     | 3306  | Optional trace 存储；不设 `MYSQL_HOST` 不连库，整栈照常起。 |
| GitLab    | 8080→80 | Optional 私有化 GitLab；不设 `GITLAB_URL`/`GITLAB_TOKEN` 不产生依赖。 |

**Optional services（无依赖）**

- **mysql**：用于 trace 双写与 Dashboard 可观测。不设 `MYSQL_HOST` 时 Queen/Dashboard 不连库，仅无 trace 落库与展示。
- **gitlab**：私有化 GitLab，供 agent 的 `gitlab_*` 工具使用。不设 `GITLAB_URL`/`GITLAB_TOKEN` 时栈照常启动；要用时在 `.env` 中设 `GITLAB_URL=http://gitlab`、`GITLAB_TOKEN=<从 GitLab 创建的 token>`，可选 `GITLAB_ROOT_PASSWORD` 作初始 root 密码。

**DB 选型（当前场景）**

- **MySQL**：多容器写 trace、Dashboard 读、可扩展，与现有 `pymysql`/`mysql2` 一致；compose 内提供可选 `mysql` 服务，不配置也能起。
- SQLite：零依赖、单文件，但多进程/多容器写同一库需共享 volume 与 WAL，且需改 ants/dashboard 两处；适合单机最小化部署，当前未采用。
- 结论：保持 **MySQL** 作为可选 trace 存储，compose 内可选起 `mysql`，不产生启动依赖。

**Image**

Default base: `python:3.14-slim`. Override in Dockerfile with `ARG PYTHON_VERSION=3.13-slim` if needed.

<details>
<summary>Environment (selection)</summary>

| Variable | Purpose |
|----------|---------|
| `ANTS_CONFIG_DIR` | Agent config directory. |
| `ANTS_AUTO_SPAWN_DEFAULT` | `1` = spawn all workers at startup. |
| `ANTS_HOST_PROJECT_ROOT`, `ANTS_IMAGE` | For spawn volume/image. |
| `MYSQL_HOST` | Optional; set to `mysql` to use in-compose MySQL. |
| `MYSQL_PASSWORD` | Optional; must match mysql service for trace dual-write. |
| `GITLAB_URL`, `GITLAB_TOKEN` | Optional; set `GITLAB_URL=http://gitlab` to use in-compose GitLab. |
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
