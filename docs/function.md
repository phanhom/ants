# Ants 技术说明（代码细节设计）

本文档说明 Ants 代码结构、模块职责、数据流与环境变量，便于维护与扩展。

---

## 1. 总体结构

```
ants/
├── ants/
│   ├── api/           # 对外与内部 HTTP 接口
│   ├── agents/        # Ant 进程入口与工具热加载
│   ├── protocol/      # AIP 协议模型
│   └── runtime/       # 配置、建员、状态、留痕
├── configs/agents/    # 员工配置模板（YAML）
├── shared/            # 共享 tools、inbox（挂载到各容器）
├── volumes/           # 按 agent_id 的留痕目录（宿主机）
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

- **对外仅两接口**：(1) **容器间对话** `POST /aip`；(2) **工作信息/状态/进度** `GET /status`。
- **蚁后 (queen)**：端口 22000；`GET /status`（聚合）、`POST /aip`（接收并转发/处理）；`POST /instruction` 为便捷入口。
- **工人**：端口 22001；仅 `POST /aip`、`GET /status`。内部 `/internal/configs`、`POST /internal/spawn` 需 Admin Token。

---

## 2. 模块说明

### 2.1 `ants.api.main`（蚁后）

- **职责**：FastAPI 应用、生命周期、路由；用户指令入口、状态聚合与 AIP 转发。
- **启动（lifespan）**：
  1. `get_config_dir()` 解析配置目录；加载 `creator_decider.yaml` 作为根配置，`load_all_agent_configs()` 得到全部 config。
  2. 为根 ant 创建留痕目录并写启动日志。
  3. 若 `ANTS_AUTO_SPAWN_DEFAULT` 为真且根配置允许建员，则 **workers = 除根外的全部 config**，用 `DockerSpawner.ensure_children(workers, extra_env=runtime_config_to_env(load_runtime_config()))` 全员建员。
- **路由**：
  - `GET /status`：支持 `scope=colony|self|subtree`；`scope=subtree` 时可带 `root=<agent_id>` 返回某一支的递归状态树。
  - `POST /aip`：接收 AIP（接口一）；若 to≠自己则按 to_base_url 或 status_api_base 或同机转发到该 ant 的 `/aip`；若 to=自己且 action=user_instruction 则拆解下发工人。
  - `POST /instruction`：便捷入口，等价向蚁后发 AIP user_instruction。
  - `GET /internal/configs`、`POST /internal/spawn`：需 `X-Admin-Token`；spawn 时注入 runtime env。

- **鉴权**：内部接口依赖 `require_admin`（`ANT_ADMIN_TOKEN` / `ANTS_ADMIN_TOKEN`）。

### 2.2 `ants.runtime.config`

- **职责**：解析配置目录、加载单份/多份员工配置。
- **关键函数**：
  - `get_config_dir()`：优先 `ANTS_CONFIG_DIR`；否则若存在 `Path.cwd()/configs/agents` 则用，否则 `/app/configs/agents`（容器内默认）。
  - `get_config_path()`：当前进程的 config 路径，由 `ANT_CONFIG` 或默认 `creator_decider.yaml`。
  - `load_agent_config(path)`：读 YAML 并校验为 `AgentConfig`。
  - `list_available_agent_ids(config_dir)`：扫描目录下 `.yaml`，返回 `agent_id` 列表。
  - `load_all_agent_configs(config_dir)`：加载全部配置，顺序为 `creator_decider` 在前，其余按目录顺序。

### 2.3 `ants.runtime.models`

- **职责**：Pydantic 模型，供配置、状态、AIP 使用。
- **主要类型**：
  - `AgentConfig`：员工模板（agent_id、display_name、role、superior、subordinates、authority_weight、skills、tools_allowed、prompt_profile、can_spawn_subordinates、max_subordinates、environment_policy 等）。
  - `PromptProfile`、`EnvironmentPolicy`：嵌套在 AgentConfig 中。
  - `AgentStatus`：运行时内部状态摘要。
  - `StatusEnvelope`：历史运行时聚合模型；当前对外协议模型已迁移到 `ants.protocol.status`。

### 2.4 `ants.runtime.docker_manager`

- **职责**：蚁后通过 Docker SDK 创建/启动工人容器；注入运行时配置 env；工人与蚁后同网（`ANTS_NETWORK`）。
- **DockerSpawner**：
  - `available()`：Docker 可用且 `ANTS_HOST_PROJECT_ROOT` 存在。
  - `ensure_volume_dirs(agent_id)`：在宿主机创建 volumes/<agent_id> 下 workspace、logs、aip、todos 等及 shared/tools、shared/inbox。
  - `_volume_binds(agent_id, config_name)`：宿主机路径 → 容器内路径。
  - `spawn_one(child, extra_env=None, command=None)`：若已存在则 start；否则创建容器，**command 默认 `python -m ants.agents.server`**，注入 `ANT_SERVICE_PORT=22001` 与 `extra_env`（如 runtime 扁平化 env）。
  - `ensure_children(children, extra_env=None)`：对每个 config 调用 `spawn_one`，返回容器名列表。

- **约定**：子容器名 `ants-<agent_id>`；工人端口 `WORKER_SERVICE_PORT=22001`；`ANTS_NETWORK` 使蚁后可访问 `http://ants-<agent_id>:22001`。

### 2.5 `ants.runtime.status`

- **职责**：从配置、留痕与 Docker 状态聚合成对外状态。
- **StatusAggregator**：
  - `volumes_root`：由 `ANTS_VOLUMES_ROOT` 或本地 fallback（cwd/volumes、/tmp/ants_volumes）决定。
  - `_container_state(agent_id)`：通过 Docker API 查询 `ants-<agent_id>` 的 status（running/exited/missing 等）。
  - `_derive_status(agent)`：读该 ant 的 todos、reports、aip、logs 的 JSONL，结合容器状态得到协议层 `SingleAntStatus`，并补充 `base_url` / `endpoints`。
  - `build(agents)`：拼成 `ColonyStatusDocument`（平铺聚合视图）。
  - `build_recursive_status_tree(...)`：将 flat status + topology 组装为递归树。
  - `build_worker_subtree_status(...)`：让管理型节点返回“当前节点 + 下级”的递归状态。

### 2.6 `ants.runtime.traces`

- **职责**：按 ant 的留痕目录读写 JSONL，统一“工作留痕”的落盘方式。
- **路径**：`get_agent_base_dir(agent_id)` 优先 `ANT_BASE_DIR`，否则 `ANTS_VOLUMES_ROOT/<agent_id>`，再否则 cwd/volumes 或 /tmp/ants_volumes（见 4.2）。
- **函数**：
  - `ensure_trace_dirs(agent_id)`：创建 workspace、logs、conversations、aip、todos、reports、context。
  - `write_log(agent_id, filename, payload)`：向 `logs/<filename>` 追加一行带 `ts` 的 JSON。
  - `list_recent_jsonl(file_path, limit)`：读文件末尾 N 行 JSONL，用于状态聚合。

### 2.6 `ants.runtime.runtime_config`

- **职责**：加载 `configs/runtime.yaml`（LLM、GitLab、MySQL；默认不含 Redis），展开 `${VAR}` 为环境变量，并扁平化为 env 供工人注入。
- **函数**：`get_runtime_config_path()`、`load_runtime_config()`、`runtime_config_to_env(conf)`（如 `llm.base_url` → `LLM_BASE_URL`）。

### 2.7 `ants.agents.server`（工人 HTTP）

- **职责**：工人容器入口；**仅两个接口**：`POST /aip`（接收 AIP、落盘、返回 ack）、`GET /status`（默认返回 self，可用 `scope=subtree` 返回递归总状态）；后台线程跑 `ants.agents.bootstrap`（工具热加载与心跳）。
- **端口**：`ANT_SERVICE_PORT`（默认 22001）。同机：`http://ants-<agent_id>:22001`；跨机：配置 `status_api_base` 或 AIP 中 `to_base_url`。

### 2.8 `ants.agents.bootstrap`

- **职责**：子容器（或单机 worker）的进程入口；加载配置、热加载共享工具、可选心跳与留痕。
- **流程**：
  1. `load_agent_config()` 加载当前 ant 配置（由 `ANT_CONFIG` 注入）。
  2. `ensure_trace_dirs(config.agent_id)`，写启动日志。
  3. 扫描 `/shared/tools` 下的 `.py` 并动态加载为模块，写技能快照到 `context/skills.jsonl`。
  4. 若配置为根且允许建员，可调用 `spawn_subordinates`（通常子容器不会带此配置）。
  5. 若 `poll=True`，进入循环：定期写心跳到 `logs/runtime.jsonl`，并再次扫描 `/shared/tools` 做热加载。

### 2.9 `ants.protocol.aip` / `ants.protocol.status`

- **职责**：AIP 协议层的可导出模型。
- **类型**：
  - `ants.protocol.aip`：`AIPStatus`、`AIPPriority`、`RouteScope`、`ApprovalState`、`AIPAction`、`AIPMessage`、`AIPAck`、`build_message()`。
  - `ants.protocol.status`：`StatusScope`、`StatusEndpoints`、`WorkStatusSnapshot`、`SingleAntStatus`、`RecursiveStatusNode`、`ColonyStatusDocument`。

---

## 3. 数据流摘要

- **状态查询**：
  - 蚁后 `GET /status?scope=colony` → `StatusAggregator.build(visible_agents)` → 返回 `ColonyStatusDocument`。
  - 蚁后 `GET /status?scope=subtree&root=<agent_id>` → `build_recursive_status_tree(...)` → 返回递归状态树。
  - 工人 `GET /status?scope=self|subtree` → `build_worker_self_status(...)` 或 `build_worker_subtree_status(...)`。
- **用户指令**：用户 `POST /instruction` 或 `POST /aip`（user_instruction）→ 蚁后拆解并转发 AIP 到工人 `POST http://ants-<agent_id>:22001/aip` → 工人落盘 aip 并返回 ack。
- **启动建员**：lifespan 中若 `ANTS_AUTO_SPAWN_DEFAULT` 为真且根允许建员，则 workers = 除根外全部 config，`ensure_children(workers, extra_env=runtime_env)`。
- **动态建员**：带 Token 调用 `POST /internal/spawn`，加载对应 YAML，`spawn_one(cfg, extra_env=runtime_env)`。

---

## 4. 环境变量与路径

### 4.1 配置目录

| 变量 | 含义 | 默认/fallback |
|------|------|----------------|
| `ANTS_CONFIG_DIR` | 员工配置目录（YAML） | 若存在 `cwd/configs/agents` 则用，否则 `/app/configs/agents` |
| `ANT_CONFIG` | 当前进程使用的单份 config 文件路径 | `get_config_dir()/creator_decider.yaml` |

### 4.2 留痕与 Volume 根路径

| 变量 | 含义 | 默认/fallback |
|------|------|----------------|
| `ANT_BASE_DIR` | 当前 ant 的留痕根目录（单 ant 进程内） | 见下 |
| `ANTS_VOLUMES_ROOT` | 所有 ant 的 volume 根（宿主机或容器内） | 无则用 `cwd/volumes` 或 `/tmp/ants_volumes` |

单 ant 的留痕根 = `ANT_BASE_DIR` 或 `ANTS_VOLUMES_ROOT/<agent_id>` 或上述 fallback。

### 4.3 建员与 Docker

| 变量 | 含义 | 默认 |
|------|------|------|
| `ANTS_HOST_PROJECT_ROOT` | **宿主机**上本仓库绝对路径（建员时 volume 绑定用） | 空则 spawner 不可用 |
| `ANTS_IMAGE` | 子容器使用的镜像名 | `ants:latest` |
| `ANTS_NETWORK` | 工人与蚁后共用的 Docker 网络（如 `ants_default`） | 无 |
| `ANTS_AUTO_SPAWN_DEFAULT` | 启动时是否自动建员（1/0 或 true/false） | `1` |

### 4.4 鉴权

| 变量 | 含义 |
|------|------|
| `ANT_ADMIN_TOKEN` 或 `ANTS_ADMIN_TOKEN` | 内部接口（/internal/configs、/internal/spawn）所需 Token；请求头 `X-Admin-Token` |

### 4.5 运行时配置

- **文件**：`configs/runtime.yaml`（路径可由 `ANTS_RUNTIME_CONFIG` 覆盖）。
- **内容**：llm、gitlab、mysql（默认不含 redis；工人若需可自建）；敏感值用 `${VAR}` 占位，由 env 注入。
- **工人**：建员时通过 `runtime_config_to_env(load_runtime_config())` 扁平化后注入容器 env（如 `LLM_BASE_URL`、`GITLAB_URL`）。

---

## 5. docker-compose 使用要点

- **服务名**：`queen`（蚁后），容器名 `ants-queen`。
- **宿主机路径**：`ANTS_HOST_PROJECT_ROOT=${PWD}`，需在仓库根执行 compose 或设置 `PWD`。
- **挂载**：当前目录挂到 `/app/host`；建员时 volume 使用宿主机路径。
- **Docker Socket**：仅挂载进 **queen**，工人不挂载（Docker-outside-of-Docker）；工人需跑容器时由蚁后代执行。
- **网络**：`ANTS_NETWORK=ants_default`，使蚁后与工人同网，蚁后访问 `http://ants-<agent_id>:22001`。
- **关闭自动建员**：`ANTS_AUTO_SPAWN_DEFAULT=0`，则启动不建员，仅通过 `POST /internal/spawn` 动态创建。

---

## 6. 扩展与维护建议

- **新增岗位**：在 `configs/agents/` 增加 `<agent_id>.yaml`，符合 `AgentConfig` 结构即可；会被 `list_available_agent_ids` 与 `load_all_agent_configs` 自动纳入，并可通过 `/internal/spawn` 按需创建。
- **AIP 收发与留痕**：`POST /aip` 接收 AIP 后通过 `append_aip_message(agent_id, "in", payload)` 写入 `aip/messages.jsonl`；跨机时发送方或蚁后根据 `to_base_url` 或 `status_api_base` 请求目标 ant 的 `/aip`。
- **工具热加载**：蚁后（或运维）在宿主机向 `shared/tools/` 放入 `.py` 后，工人容器内 server 后台的 bootstrap 轮询会加载新模块，无需重启容器。
