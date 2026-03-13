# AIP — Agent Interaction Protocol

AIP is the sole communication protocol for the Nest + Ants system. All agent-to-agent and user-to-agent interactions flow through AIP.

The protocol is defined and maintained in the [aip-protocol SDK](https://github.com/phanhom/aip) (v1.3.0). This document describes how AIP is used within the Nest + Ants architecture.

---

## 1. Protocol Overview

AIP defines two things:

- **Status protocol**: Who an agent is, where it is, what it's doing, and how its subordinates are doing.
- **Messaging protocol**: How agents and users send structured messages to each other.

### Design Goals

- **Unified**: Users, Queen, and workers all use the same wire format.
- **Addressable**: Same-machine and cross-machine addressing without a central lookup.
- **Discoverable**: One `GET /status` response tells the caller where to send `/aip`.
- **Recursive**: Any node can return "myself + all subordinates" as a tree.
- **Exportable**: Protocol models are decoupled from runtime — third parties can depend on `aip-protocol`.

### Transport

- Intra-cluster: HTTP (e.g. `http://ants-backend:22001`)
- Cross-machine: HTTP (e.g. `https://backend.region.example.com`)
- Wire format: JSON over HTTP POST

---

## 2. Addressing

### In the Nest + Ants Architecture

With the Nest platform, addressing has a clear two-tier model:

1. **Via Nest router**: Send to `POST {nest_url}/v1/aip` with the `to` field set to the target agent. Nest resolves the agent's base_url from its registry and forwards.
2. **Direct**: Send to `POST {agent_base_url}/v1/aip` directly if you know the agent's address.

### Address Resolution Priority

When Queen sends to a worker:

1. `to_base_url` in the AIP message (explicit override)
2. `status_api_base` from the agent's config
3. Default: `http://ants-{agent_id}:22001`

### Self-describing Status

Status responses include addressing information for discovery:

| Field | Type | Description |
|-------|------|-------------|
| `base_url` | string | Agent's accessible base URL |
| `endpoints.aip` | string | AIP message endpoint |
| `endpoints.status` | string | Status endpoint |

---

## 3. Status Protocol

### Query Scopes

| Scope | Description | Available on |
|-------|-------------|-------------|
| `self` | Current agent only | All agents |
| `subtree` | Agent + all subordinates (recursive tree) | All agents |
| `group` / `colony` | All registered agents (flat list) | Nest |

### AgentStatus

Each agent's status includes:

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Unique identifier |
| `role` | string | Functional role |
| `namespace` | string | Namespace (default: "default") |
| `superior` | string | Parent agent ID |
| `authority_weight` | int | Organizational weight |
| `lifecycle` | string | `running` / `degraded` / `failed` |
| `ok` | boolean | Whether agent is healthy |
| `base_url` | string | Agent's base URL |
| `endpoints` | object | Discoverable endpoints (aip, status) |
| `pending_tasks` | int | Number of pending tasks |
| `last_seen_at` | string | Last heartbeat time (ISO) |

### GroupStatus

Returned by Nest for `scope=group`:

```json
{
  "root_agent_id": "creator_decider",
  "topology": {
    "creator_decider": ["backend", "frontend_uiux", "qa", "explorer", "bizdev"]
  },
  "waiting_for_approval": false,
  "agents": [ ...AgentStatus objects... ]
}
```

### RecursiveStatusNode

Returned for `scope=subtree`:

```json
{
  "self": { ...AgentStatus... },
  "subordinates": [
    {
      "self": { ...AgentStatus... },
      "subordinates": []
    }
  ]
}
```

### Lifecycle Derivation

In the Nest architecture, lifecycle is derived from heartbeat freshness (not container state):

| Lifecycle | Condition |
|-----------|-----------|
| `running` | Last heartbeat < 30s ago |
| `degraded` | Last heartbeat 30s–120s ago |
| `failed` | Last heartbeat > 120s ago |

Thresholds are configurable in `nest.json` → `registry.heartbeat_timeout` / `registry.heartbeat_dead`.

---

## 4. Messaging Protocol

### AIPMessage

Full field reference — see [api.md](api.md) for the wire format table.

Key fields:

| Layer | Fields |
|-------|--------|
| **Routing** | `version`, `message_id`, `from`, `to`, `to_base_url`, `route_scope` |
| **Execution** | `action`, `intent`, `payload`, `expected_output`, `constraints`, `priority`, `status` |
| **Governance** | `authority_weight`, `requires_approval`, `approval_state` |
| **Observability** | `trace_id`, `correlation_id`, `retries`, `latency_ms`, `error_code` |

### Standard Actions

| Action | Typical Flow |
|--------|-------------|
| `user_instruction` | User → Queen |
| `assign_task` | Queen → Worker |
| `submit_report` | Worker → Queen |
| `request_context` | Any → Any |
| `request_approval` | Agent → User |
| `escalate` | Worker → Queen |
| `handoff` | Worker → Worker |

### Send Reliability

The SDK provides `async_send` and `async_send_batch` with configurable retry and backoff:

```python
from aip import SendParams, async_send, async_send_batch

params = SendParams(timeout=30, max_retries=4, backoff_base=1.0, backoff_max=30.0)
result = await async_send(base_url, message_body, params=params)
```

Retry policy: retries on 5xx and connection errors; does not retry 4xx.

---

## 5. Registration and Heartbeat

New in the Nest architecture — agents register themselves and maintain presence:

### Registration Flow

```
Agent starts
  ↓
POST {nest_url}/v1/registry/agents
  { agent_id, base_url, role, superior, subordinates, endpoints }
  ↓
Nest returns { heartbeat_url }
  ↓
Agent starts heartbeat loop (every 10s)
  POST {nest_url}{heartbeat_url}
  { ok: true, lifecycle: "running", pending_tasks: 0 }
```

### Deregistration

On graceful shutdown:

```
DELETE {nest_url}/v1/registry/agents/{agent_id}
```

### Remote Agent Registration

Any agent (not just Ants-created agents) can register with Nest by calling the registry API. This enables:

- Remote agents from other hosts
- Agents created by different systems
- Manual connection via the Nest dashboard

---

## 6. Trace Events

Agents post structured trace events to Nest:

```
POST {nest_url}/v1/traces
{
  "agent_id": "backend",
  "trace_type": "llm_usage",
  "payload": { ... }
}
```

Common trace types:

| Type | Description |
|------|-------------|
| `registry` | Registration/deregistration events |
| `aip` | AIP message routing events |
| `llm_usage` | LLM token usage and cost |
| `llm_call` | Individual LLM call details |
| `tool_call` | Tool execution events |
| `user_instruction` | User instruction receipt |
| `assign_task` | Task assignment events |

---

## 7. Conversation Examples

### User → Nest → Queen

```
User: POST http://localhost:22000/instruction
  { "instruction": "Design the order service API" }

Nest wraps as AIP user_instruction, routes to creator_decider

Queen decomposes:
  → assign_task to backend: "Design REST API contract"
  → assign_task to qa: "Plan integration tests for order API"
```

### Agent → Agent (via Nest router)

```
POST http://nest:22000/v1/aip
{
  "from": "backend",
  "to": "frontend_uiux",
  "action": "request_context",
  "intent": "Need API schema for frontend integration",
  "payload": { "topic": "order API schema" }
}
```

### Worker → Queen (direct)

```
POST http://ants-queen:22100/v1/aip
{
  "from": "backend",
  "to": "creator_decider",
  "action": "submit_report",
  "intent": "Order API design complete",
  "payload": { "artifacts": ["openapi/orders.yaml"] }
}
```

---

## 8. SDK Reference

The protocol is implemented in the [aip-protocol](https://github.com/phanhom/aip) Python SDK:

```bash
pip install "aip-protocol @ git+https://github.com/phanhom/aip.git@v1.3.0#subdirectory=sdk-python"
```

Key exports:

| Module | Exports |
|--------|---------|
| `aip` | `AIPMessage`, `AIPAction`, `AIPStatus`, `AIPAck` |
| `aip` | `AgentStatus`, `GroupStatus`, `RecursiveStatusNode`, `StatusEndpoints` |
| `aip` | `SendParams`, `async_send`, `async_send_batch`, `send`, `send_batch` |
| `aip` | `TraceEvent`, `LLMUsage`, `WorkSnapshot` |

Protocol version: `1.0` (backwards-compatible additions only).
