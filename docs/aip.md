# AIP — Ants Interaction Protocol

AIP 是 Ants 的唯一正式协作协议。它同时定义两件事：

- **状态协议**：一个人/容器现在是谁、在哪、正在做什么、下级总状态如何。
- **对话协议**：人和容器、容器和容器之间如何收发结构化消息。

目标不是只给 Ants 自己用，而是让 AIP 未来可以像 MCP 或 OpenAI 的线协议那样，被不同系统、不同语言、不同服务器直接实现和复用。

---

## 1. 协议定位

### 1.1 设计目标

- **统一**：用户、蚁后、工人都走同一套 AIP 线格式。
- **可寻址**：同机与跨机都能定位目标，不依赖中心注册表。
- **可发现**：拿到一次 `GET /status`，调用方就能知道后续该往哪里发 `/aip`。
- **可递归**：任意节点都可以返回“我自己 + 我的下级”的总状态。
- **可导出库**：协议模型与运行时解耦，第三方可以直接依赖 `ants.protocol`。
- **可演进**：新增字段和动作以向后兼容为原则。

### 1.2 传输约定

- 同机：HTTP，如 `http://ants-backend:22001`。
- 跨机：HTTP，如 `https://backend.region.example.com`。
- 当前协议以 JSON 为主，后续可在不破坏字段语义的前提下扩展为流式帧传输。

---

## 2. 寻址与可发现性

### 2.1 请求时要不要“带 IP”

**结论：不需要。**

调用方请求状态时，本身就是向一个已经确定的地址发请求：

- `GET http://ants-backend:22001/status`
- `GET https://backend.region.example.com/status`

也就是说，**地址由请求目标 URL 决定**，不是由请求体再额外携带一个 IP 决定。

### 2.2 为什么状态响应里还要带地址

虽然请求时不需要“带 IP”，但**状态响应应该尽量自描述**，这样：

- SDK 拿到一次状态后，就知道下一步往哪里发 `/aip`
- 跨机协作时，调用方不需要额外查配置中心
- AIP 作为库输出时，发现和寻址逻辑更标准

因此，AIP 建议每个状态响应都可包含：

| 字段 | 类型 | 含义 |
|------|------|------|
| `base_url` | string \| null | 当前节点可被访问的 base URL |
| `endpoints.aip` | string \| null | 当前节点的对话入口 |
| `endpoints.status` | string \| null | 当前节点的状态入口 |

### 2.3 寻址优先级

发送 AIP 消息时，目标地址按以下优先级确定：

1. 消息内 `to_base_url`
2. 目标配置中的 `status_api_base`
3. 同机默认地址
   - 工人：`http://ants-<agent_id>:22001`
   - 蚁后：`http://ants-queen:22000`

---

## 3. 状态协议

状态协议只通过 `GET /status` 暴露。

### 3.1 查询范围（scope）

| scope | 适用对象 | 含义 |
|------|----------|------|
| `self` | 工人 / 蚁后 | 只返回当前节点自身状态 |
| `subtree` | 工人 / 蚁后 | 返回当前节点或指定根节点及其所有下级的递归树 |
| `colony` | 蚁后 | 返回整巢平铺聚合视图 |

约定：

- 工人默认：`scope=self`
- 蚁后默认：`scope=colony`
- 蚁后支持：`GET /status?scope=subtree&root=<agent_id>`

### 3.2 单节点状态（SingleAntStatus）

单节点状态既可作为工人的直接响应，也可作为聚合列表中的一个元素，还可作为递归树中的 `self` 节点。

| 字段 | 类型 | 含义 |
|------|------|------|
| `agent_id` | string | 当前节点唯一标识 |
| `role` | string | 当前节点角色 |
| `superior` | string \| null | 上级节点 |
| `authority_weight` | int \| null | 权威权重 |
| `lifecycle` | string \| null | 生命周期：`idle` / `starting` / `running` / `blocked` / `degraded` / `failed` |
| `port` | int \| null | 服务端口 |
| `ok` | boolean | 节点是否可用 |
| `base_url` | string \| null | 当前节点 base URL |
| `endpoints` | object \| null | 可发现端点 |
| `pending_todos` | int | 未完成待办数 |
| `recent_errors` | int | 近期错误数 |
| `waiting_for_approval` | boolean | 是否等待人审 |
| `last_report_at` | string \| null | 最后汇报时间 |
| `last_aip_at` | string \| null | 最后 AIP 时间 |
| `last_seen_at` | string \| null | 最后活动时间 |
| `container_name` | string \| null | 容器名 |
| `container_state` | string \| null | 容器状态 |
| `work` | object \| null | 工作快照，见 3.3 |

### 3.3 工作快照（WorkStatusSnapshot）

| 字段 | 类型 | 含义 |
|------|------|------|
| `todos` | array | 最近待办 |
| `reports` | array | 最近汇报 |
| `recent_aip` | array | 最近收发的 AIP 报文 |
| `last_seen` | string \| null | 最近活动时间 |
| `pending_todos` | int | 未完成待办数量 |

### 3.4 工人 `GET /status`

工人默认返回 `scope=self` 的单节点状态。

示例：

```json
{
  "agent_id": "backend",
  "role": "backend_engineer",
  "superior": "creator_decider",
  "authority_weight": 78,
  "lifecycle": "running",
  "port": 22001,
  "ok": true,
  "base_url": "https://backend.region.example.com",
  "endpoints": {
    "aip": "https://backend.region.example.com/aip",
    "status": "https://backend.region.example.com/status"
  },
  "pending_todos": 2,
  "recent_errors": 0,
  "waiting_for_approval": false,
  "last_report_at": "2026-03-07T12:00:00Z",
  "last_aip_at": "2026-03-07T12:03:00Z",
  "last_seen_at": "2026-03-07T12:05:00Z",
  "work": {
    "todos": [],
    "reports": [],
    "recent_aip": [],
    "last_seen": "2026-03-07T12:05:00Z",
    "pending_todos": 2
  }
}
```

### 3.5 递归状态（RecursiveStatusNode）

递归状态用于表达“当前节点 + 所有下级”的总状态。

结构：

```json
{
  "self": { "...SingleAntStatus..." : "..." },
  "subordinates": [
    {
      "self": { "...SingleAntStatus..." : "..." },
      "subordinates": []
    }
  ]
}
```

这适用于：

- 蚁后看整棵组织树
- 任意管理者看自己这一支
- 未来多层管理节点的递归聚合

示例：

```json
{
  "self": {
    "agent_id": "creator_decider",
    "role": "creator_decider",
    "lifecycle": "running",
    "base_url": "https://queen.example.com",
    "endpoints": {
      "aip": "https://queen.example.com/aip",
      "status": "https://queen.example.com/status"
    }
  },
  "subordinates": [
    {
      "self": {
        "agent_id": "backend",
        "role": "backend_engineer",
        "lifecycle": "running",
        "base_url": "https://backend.region.example.com"
      },
      "subordinates": []
    }
  ]
}
```

### 3.6 整巢状态（ColonyStatusDocument）

蚁后默认返回整巢平铺聚合视图，适合 dashboard、告警和批量扫描。

| 字段 | 类型 | 含义 |
|------|------|------|
| `ok` | boolean | 整体是否正常 |
| `service` | string | 服务标识 |
| `port` | int | 蚁后端口 |
| `root_agent_id` | string | 根节点 |
| `timestamp` | string | 生成时间 |
| `topology` | object | agent_id 到直属下级列表的映射 |
| `waiting_for_approval` | boolean | 整巢是否存在待审批 |
| `ants` | array | 所有节点的 `SingleAntStatus` 列表 |

示例：

```json
{
  "ok": true,
  "service": "ants",
  "port": 22000,
  "root_agent_id": "creator_decider",
  "timestamp": "2026-03-07T12:06:00Z",
  "topology": {
    "creator_decider": ["backend", "frontend_uiux", "qa", "explorer", "bizdev"]
  },
  "waiting_for_approval": false,
  "ants": [
    {
      "agent_id": "creator_decider",
      "role": "creator_decider",
      "base_url": "https://queen.example.com",
      "endpoints": {
        "aip": "https://queen.example.com/aip",
        "status": "https://queen.example.com/status"
      }
    },
    {
      "agent_id": "backend",
      "role": "backend_engineer",
      "base_url": "https://backend.region.example.com",
      "endpoints": {
        "aip": "https://backend.region.example.com/aip",
        "status": "https://backend.region.example.com/status"
      }
    }
  ]
}
```

### 3.7 状态推导原则

- `lifecycle` 由留痕与容器状态共同推导。
- 状态数据不依赖实时内存，可由 `todos`、`reports`、`aip`、`logs` 回放。
- `base_url` 与 `endpoints` 用于**发现**，不是必需字段；未知时可为 `null`。

---

## 4. 对话协议

对话以单条 AIP JSON 报文为最小单位，通过 `POST /aip` 发送。

### 4.1 消息层次

- **协议层**：版本、收发方、路由范围、优先级、时间戳。
- **治理层**：权威权重、审批状态、父任务链路。
- **执行层**：动作、意图、载荷、期望输出、约束。
- **可观测层**：重试次数、处理延迟、错误码、错误信息。

### 4.2 AIPMessage 字段

#### 基础与路由

| 字段 | 类型 | 必填 | 含义 |
|------|------|------|------|
| `version` | string | 是 | 协议版本，如 `\"1.0\"` |
| `message_id` | string | 是 | 消息唯一 ID |
| `correlation_id` | string \| null | 否 | 请求-响应链路 ID |
| `trace_id` | string \| null | 否 | 全链路追踪 ID |
| `parent_task_id` | string \| null | 否 | 父任务 ID |
| `from` | string | 是 | 发送方，容器或 `\"user\"` |
| `to` | string | 是 | 接收方 agent_id，或 `\"*\"` |
| `from_role` | string \| null | 否 | 发送方角色，如 `\"user\"`、`\"backend_engineer\"` |
| `to_role` | string \| null | 否 | 接收方角色 |
| `to_host` | string \| null | 否 | 目标主机信息 |
| `to_base_url` | string \| null | 否 | 目标节点完整 base URL |
| `route_scope` | string | 否 | `\"local\"` 或 `\"remote\"` |

#### 执行与治理

| 字段 | 类型 | 必填 | 含义 |
|------|------|------|------|
| `action` | string | 是 | 标准动作 |
| `intent` | string | 是 | 人类可读的意图 |
| `payload` | object | 否 | 结构化载荷 |
| `expected_output` | string \| null | 否 | 希望返回的产物或结果 |
| `constraints` | array of string | 否 | 策略、时限、上下文约束 |
| `priority` | string | 否 | `low` / `normal` / `high` / `urgent` |
| `status` | string | 否 | `Pending` / `InProgress` / `Completed` / `Failed` |
| `authority_weight` | int | 否 | 发送方权威权重 |
| `requires_approval` | boolean | 否 | 是否需要人审 |
| `approval_state` | string | 否 | `not_required` / `waiting_human` / `approved` / `rejected` |

#### 可观测与时间

| 字段 | 类型 | 含义 |
|------|------|------|
| `retries` | int | 重试次数 |
| `latency_ms` | int \| null | 处理耗时 |
| `error_code` | string \| null | 错误码 |
| `error_message` | string \| null | 错误信息 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 4.3 标准动作

| action | 含义 |
|--------|------|
| `assign_task` | 指派任务 |
| `request_context` | 请求上下文 |
| `request_artifact_review` | 请求产物评审 |
| `submit_report` | 提交汇报 |
| `request_approval` | 请求审批 |
| `publish_status` | 发布状态 |
| `handoff` | 工作交接 |
| `escalate` | 升级问题 |
| `tool_result` | 工具调用结果 |
| `sync_skill_registry` | 同步技能注册表 |
| `user_instruction` | 用户指令，通常发给蚁后，也可直达某个工人 |

### 4.4 `POST /aip`

请求：

- Method: `POST`
- Path: `/aip`
- Body: 一条 `AIPMessage`

标准 ack：

```json
{
  "ok": true,
  "message_id": "8e9930a2-8b58-44ad-a642-4cc1f136cc5d",
  "to": "backend",
  "status": "received",
  "correlation_id": "corr-001"
}
```

状态码约定：

- `200`：成功接收
- `400`：目标错误，例如 `to` 与当前容器不匹配
- `422`：报文格式不合法
- `503`：上游或转发目标不可达

### 4.5 留痕

每条 AIP 消息必须写入：

- `aip/messages.jsonl`
- 必要时 `logs/runtime.jsonl`

这也是 `GET /status` 中 `recent_aip` 的来源。

---

## 5. 完整对话示例

### 5.1 用户直达蚁后

请求：

- URL: `POST https://queen.example.com/aip`

```json
{
  "version": "1.0",
  "message_id": "msg-user-001",
  "correlation_id": "corr-user-001",
  "trace_id": "trace-user-001",
  "parent_task_id": "task-launch-001",
  "from": "user",
  "to": "creator_decider",
  "from_role": "user",
  "to_role": "creator_decider",
  "route_scope": "remote",
  "action": "user_instruction",
  "intent": "让后端先设计订单服务 API",
  "payload": {
    "instruction": "先定义订单服务接口，再给我一个风险清单"
  },
  "expected_output": "A delegated task and a report plan",
  "constraints": [
    "start in test",
    "production requires human approval"
  ],
  "priority": "high",
  "status": "Pending",
  "authority_weight": 100,
  "requires_approval": false,
  "approval_state": "not_required",
  "retries": 0,
  "created_at": "2026-03-07T12:10:00Z",
  "updated_at": "2026-03-07T12:10:00Z"
}
```

响应：

```json
{
  "ok": true,
  "message_id": "msg-user-001",
  "to": "backend",
  "status": "received"
}
```

### 5.2 蚁后派单给工人

请求：

- URL: `POST http://ants-backend:22001/aip`

```json
{
  "version": "1.0",
  "message_id": "msg-queen-001",
  "correlation_id": "corr-user-001",
  "trace_id": "trace-user-001",
  "parent_task_id": "task-launch-001",
  "from": "creator_decider",
  "to": "backend",
  "from_role": "creator_decider",
  "to_role": "backend_engineer",
  "route_scope": "local",
  "action": "assign_task",
  "intent": "定义订单服务 API 契约",
  "payload": {
    "instruction": "先设计 REST API、错误码和 schema，再汇报",
    "deliverables": ["openapi", "risk_report"]
  },
  "expected_output": "OpenAPI draft and risk summary",
  "constraints": [
    "test first",
    "do not deploy to production"
  ],
  "priority": "high",
  "status": "Pending",
  "authority_weight": 95,
  "requires_approval": false,
  "approval_state": "not_required",
  "retries": 0,
  "created_at": "2026-03-07T12:11:00Z",
  "updated_at": "2026-03-07T12:11:00Z"
}
```

响应：

```json
{
  "ok": true,
  "message_id": "msg-queen-001",
  "to": "backend",
  "status": "received"
}
```

### 5.3 工人回报给蚁后

请求：

- URL: `POST https://queen.example.com/aip`

```json
{
  "version": "1.0",
  "message_id": "msg-backend-001",
  "correlation_id": "corr-user-001",
  "trace_id": "trace-user-001",
  "parent_task_id": "task-launch-001",
  "from": "backend",
  "to": "creator_decider",
  "from_role": "backend_engineer",
  "to_role": "creator_decider",
  "route_scope": "remote",
  "action": "submit_report",
  "intent": "提交订单服务接口初稿",
  "payload": {
    "summary": "已完成接口初稿，待确认鉴权方式",
    "artifacts": ["openapi/orders.yaml"],
    "blockers": ["auth strategy not confirmed"]
  },
  "expected_output": "Review or follow-up questions",
  "constraints": [],
  "priority": "normal",
  "status": "Completed",
  "authority_weight": 78,
  "requires_approval": false,
  "approval_state": "not_required",
  "retries": 0,
  "created_at": "2026-03-07T12:20:00Z",
  "updated_at": "2026-03-07T12:20:00Z"
}
```

响应：

```json
{
  "ok": true,
  "message_id": "msg-backend-001",
  "to": "creator_decider",
  "status": "received"
}
```

### 5.4 用户直连某个工人

这与容器间对话**完全兼容**，只需要把发送方的 `from_role` 设为 `user`。

请求：

- URL: `POST https://backend.region.example.com/aip`

```json
{
  "version": "1.0",
  "message_id": "msg-user-002",
  "from": "user",
  "to": "backend",
  "from_role": "user",
  "to_role": "backend_engineer",
  "route_scope": "remote",
  "action": "request_context",
  "intent": "直接询问当前后端进度",
  "payload": {
    "question": "你现在卡在哪里？"
  },
  "priority": "normal",
  "status": "Pending",
  "authority_weight": 100,
  "requires_approval": false,
  "approval_state": "not_required",
  "retries": 0,
  "created_at": "2026-03-07T12:30:00Z",
  "updated_at": "2026-03-07T12:30:00Z"
}
```

响应：

```json
{
  "ok": true,
  "message_id": "msg-user-002",
  "to": "backend",
  "status": "received"
}
```

### 5.5 跨机直连

请求：

- URL: `POST https://gateway.example.com/aip`

```json
{
  "version": "1.0",
  "message_id": "msg-cross-001",
  "from": "explorer",
  "to": "backend",
  "from_role": "explorer",
  "to_role": "backend_engineer",
  "to_base_url": "https://backend.region.example.com",
  "route_scope": "remote",
  "action": "request_context",
  "intent": "请求订单接口的上下文",
  "payload": {
    "topic": "order API assumptions"
  },
  "priority": "normal",
  "status": "Pending",
  "authority_weight": 60,
  "requires_approval": false,
  "approval_state": "not_required",
  "retries": 0,
  "created_at": "2026-03-07T12:40:00Z",
  "updated_at": "2026-03-07T12:40:00Z"
}
```

响应：

```json
{
  "ok": true,
  "message_id": "msg-cross-001",
  "to": "backend",
  "status": "received"
}
```

---

## 6. 用户直连兼容约定

用户不是特殊协议分支，而是 AIP 的一个普通发送方：

- `from: "user"`
- `from_role: "user"` 可选但推荐
- `to` 为目标容器的 `agent_id`

这意味着：

- 用户可以对蚁后发消息
- 用户可以直接对任意工人发消息
- 接收方不需要切换协议栈，只需要在权限、展示和审计层识别 `from_role=user`

---

## 7. 审批与治理

- 任何可能影响正式环境的消息都应设置 `requires_approval: true`
- 在 `approval_state=approved` 前不得执行正式环境动作
- **Runner 硬性拦截**：对 `write_file`、`edit_file`、`run_bash` 等工具，若调用参数带 `target_env=production`（或 `target=production`），且 agent 的 `environment_policy.production_requires_human_approval` 为真，则仅在当前任务 payload 中 `approval_state=approved` 时执行，否则返回 "Blocked: production action requires human approval."
- `authority_weight` 用于表达组织中的说话权重，不等于强制权限，但可用于路由、排序、审批策略

---

## 8. 协议作为库导出

当前建议把以下模型作为稳定导出表面：

- `ants.protocol.aip`
  - `AIPMessage`
  - `AIPAck`
  - `AIPAction`
  - `AIPStatus`
  - `ApprovalState`
  - `build_message()`
- `ants.protocol.status`
  - `StatusScope`
  - `StatusEndpoints`
  - `WorkStatusSnapshot`
  - `SingleAntStatus`
  - `RecursiveStatusNode`
  - `ColonyStatusDocument`

原则：

- 协议模型不依赖运行时编排逻辑
- 新增字段尽量可选
- 主版本不变时保持反序列化兼容

---

## 9. 与当前实现对应

| 能力 | 接口 | 代码位置 |
|------|------|----------|
| 单节点状态 | `GET /status?scope=self` | `ants.agents.server`、`ants.runtime.status` |
| 递归状态 | `GET /status?scope=subtree` | `ants.api.main`、`ants.agents.server`、`ants.runtime.status` |
| 整巢平铺状态 | `GET /status?scope=colony` | `ants.api.main`、`ants.runtime.status` |
| 对话入口 | `POST /aip` | `ants.api.main`、`ants.agents.server` |
| 用户便捷入口 | `POST /instruction` | 等价于发 `user_instruction` 到蚁后 |
| 协议模型 | — | `ants.protocol.aip`、`ants.protocol.status` |

---

## 10. 版本与扩展

- **当前协议版本**：`1.0`
- **兼容性承诺**：新增字段均为可选，不破坏现有客户端；实现可依赖 `ants.protocol` 包内 `__version__` 与文档一致。
- 后续若增加流式模式，应在不破坏现有 JSON 消息语义的前提下扩展。
- 新增动作、状态字段、发现字段时，优先使用可选字段保持向后兼容。
