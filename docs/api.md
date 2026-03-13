# API Reference

Complete endpoint reference for Nest and Ants services.

---

## Nest API (:22000)

### Registry

#### Register Agent

```
POST /v1/registry/agents
```

**Request body:**

```json
{
  "agent_id": "backend",
  "base_url": "http://ants-backend:22001",
  "namespace": "default",
  "role": "backend_engineer",
  "superior": "creator_decider",
  "subordinates": [],
  "authority_weight": 78,
  "endpoints": {
    "aip": "http://ants-backend:22001/v1/aip",
    "status": "http://ants-backend:22001/v1/status"
  },
  "tags": [],
  "display_name": "Backend Engineer"
}
```

**Response:**

```json
{
  "heartbeat_url": "/v1/registry/agents/backend/heartbeat"
}
```

#### Heartbeat

```
POST /v1/registry/agents/{agent_id}/heartbeat
```

**Request body:**

```json
{
  "ok": true,
  "lifecycle": "running",
  "pending_tasks": 0,
  "timestamp": "2026-03-13T10:00:00Z"
}
```

**Response:**

```json
{ "ok": true }
```

#### Deregister

```
DELETE /v1/registry/agents/{agent_id}
```

**Response:**

```json
{ "ok": true }
```

---

### Agent Discovery

#### List Agents

```
GET /v1/agents
```

Returns an array of `AgentStatus` objects for all registered agents.

#### Single Agent Status

```
GET /v1/agents/{agent_id}/status
```

Returns the `AgentStatus` for one agent.

---

### Status

#### Group / Subtree Status

```
GET /v1/status?scope={scope}&root={root}
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `scope` | `group`, `colony`, `subtree`, `self` | Query scope |
| `root` | agent_id | Required for `subtree` and `self` scopes |

- `scope=group` or `scope=colony`: Returns `GroupStatus` with all agents, topology, and statuses.
- `scope=subtree`: Returns `RecursiveStatusNode` rooted at `root` (defaults to root agent).
- `scope=self`: Returns `AgentStatus` for the specified `root` agent.

---

### AIP Routing

#### Route by `to` Field

```
POST /v1/aip
POST /aip
```

Accepts a full `AIPMessage` JSON body. Resolves the `to` field against the registry and forwards to the target agent's AIP endpoint.

**Status codes:**

| Code | Meaning |
|------|---------|
| 200 | Forwarded successfully |
| 404 | Target agent not registered |
| 422 | Invalid AIP message |
| 503 | Target agent unreachable |

#### Send to Specific Agent

```
POST /v1/agents/{agent_id}/aip
```

Bypasses `to` field resolution — sends directly to the specified agent.

---

### Instruction

```
POST /instruction
```

Convenience endpoint. Wraps user text as an AIP `user_instruction` message and routes to the root agent.

**Request body:**

```json
{
  "instruction": "Design the order service API",
  "task_id": "optional-task-id"
}
```

---

### Traces

#### Submit Traces

```
POST /v1/traces
```

Accepts a single trace event or an array of events.

```json
{
  "agent_id": "backend",
  "trace_type": "llm_usage",
  "payload": {
    "model": "gpt-4",
    "prompt_tokens": 1200,
    "completion_tokens": 350,
    "estimated_cost_usd": 0.058
  }
}
```

#### Query Traces

```
GET /v1/traces?agent_id={id}&trace_type={type}&since={iso}&limit={n}
```

All parameters are optional. Returns an array of trace events ordered by most recent first.

---

### Usage

```
GET /v1/usage?agent_id={id}&since={iso}
```

Returns aggregated LLM cost and token usage.

```json
{
  "total_prompt_tokens": 15000,
  "total_completion_tokens": 4500,
  "total_cost_usd": 0.42,
  "total_calls": 12,
  "by_agent": {
    "backend": { "prompt_tokens": 8000, "completion_tokens": 2500, "total_calls": 7, "cost": 0.25 }
  }
}
```

---

### Health

```
GET /health
```

```json
{ "ok": true, "agents": 6 }
```

---

## Queen API (:22100)

### AIP Receive

```
POST /v1/aip
POST /aip
```

Handles incoming AIP messages:

- If `to` != self: forwards to target worker
- If `action` = `user_instruction`: decomposes via LLM and delegates as `assign_task` batch
- Otherwise: acknowledges receipt

### Status

```
GET /v1/status
GET /status
```

Returns basic self-status for the Queen:

```json
{
  "agent_id": "creator_decider",
  "role": "creator_decider",
  "lifecycle": "running",
  "ok": true
}
```

---

## Worker API (:22001)

### AIP Receive

```
POST /v1/aip
POST /aip
```

Handles incoming AIP messages — typically `assign_task`. The worker processes the task through its LLM runner.

### Status

```
GET /v1/status
GET /status
```

Returns self-status for the worker.

---

## AIP Message Format

All AIP messages follow the `AIPMessage` schema from the [aip-protocol SDK](https://github.com/phanhom/aip):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | yes | Protocol version (e.g. `"1.0"`) |
| `message_id` | string | yes | Unique message ID (auto-generated if omitted) |
| `from` | string | yes | Sender agent_id or `"user"` |
| `to` | string | yes | Target agent_id or `"*"` |
| `action` | string | yes | Standard action (see below) |
| `intent` | string | yes | Human-readable intent |
| `payload` | object | no | Structured data |
| `trace_id` | string | no | End-to-end trace ID |
| `correlation_id` | string | no | Request-response correlation |
| `priority` | string | no | `low` / `normal` / `high` / `urgent` |
| `status` | string | no | `Pending` / `InProgress` / `Completed` / `Failed` |

### Standard Actions

| Action | Description |
|--------|-------------|
| `user_instruction` | User instruction (typically to Queen) |
| `assign_task` | Assign a task to a worker |
| `submit_report` | Worker report to superior |
| `request_context` | Request information |
| `request_artifact_review` | Request artifact review |
| `request_approval` | Request human approval |
| `publish_status` | Broadcast status update |
| `handoff` | Work handoff between agents |
| `escalate` | Escalate an issue |
| `tool_result` | Tool execution result |

---

## Standard Response (AIP Ack)

```json
{
  "ok": true,
  "message_id": "msg-id",
  "to": "agent_id",
  "status": "received"
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 200 | Success |
| 400 | Bad request |
| 404 | Agent not found |
| 422 | Invalid message format |
| 503 | Target unreachable |
