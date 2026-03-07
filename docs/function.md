# Ants — 设计与实现（技术说明）

单一文档：产品与架构 + 实现与运维。设计即基线，实现即细节。**以本文档（function.md）为唯一设计/实现参考。**

---

## I 设计

### 1. 产品定义

- **产品名**：Ants
- **形态**：多智能体协作系统；每个 Ant 为独立 Docker 容器。
- **技术栈**：全 Python（FastAPI、Pydantic、Docker SDK、PyYAML）。
- **对外**：仅两类能力——**容器间对话**（`POST /aip`）与**工作信息/状态/进度**（`GET /status`）。

### 2. 拓扑与角色

- **蚁后 (queen)**：根容器，对应 `creator_decider`；接收用户指令，拆解后通过 AIP 下发给工人。
- **工人 (workers)**：`configs/agents/` 下除蚁后外的配置各对应一容器；暴露 `POST /aip`、`GET /status`。
- **用户**：老板的上级；经 `POST /instruction` 或 `POST /aip`（user_instruction）与蚁后交互。
- **关系**：有向图；边从上级指向下级；扩岗在配置层完成，运行时代码不写死岗位名。

**启动**：蚁后启动后若 `ANTS_AUTO_SPAWN_DEFAULT=1`，为 config 下除自己外的所有人各建一容器；否则可通过 `POST /internal/spawn` 动态建员。

### 3. 对外接口（仅两个）

| 接口 | 路径 | 语义 |
|------|------|------|
| 容器间对话 | `POST /aip` | 收发 AIP 消息；接收方落盘并返回 ack。蚁后可转发（同机或 to_base_url 跨机）；若 to=自己且 action=user_instruction 则拆解下发。 |
| 状态/进度 | `GET /status` | 本节点或聚合状态。蚁后：scope=colony|self|subtree；工人：scope=self|subtree。 |

- **寻址**：请求目标 URL 即地址，无需在 body 再带 IP；响应可含 `base_url`/`endpoints` 便于发现下一跳。
- **其他**：蚁后提供 `POST /instruction`（等价 user_instruction）；`GET /internal/configs`、`POST /internal/spawn` 需 Admin Token。

### 4. 组织与员工模型

- 每人可由配置描述：agent_id、display_name、role、superior、subordinates、authority_weight、skills、tools_allowed、prompt_profile、can_spawn_subordinates、environment_policy、token_ref、status_api_base 等。
- 默认岗位：creator_decider、backend、frontend_uiux、qa、explorer、bizdev；新增岗位在 `configs/agents/` 增加 YAML 即可。

### 5. 技能与工具

- **skills**：抽象能力（如 api_design、accessibility_review）。
- **tools_allowed**：可调用工具白名单；工具来自 `/shared/tools` 热加载，无需重启容器。

### 6. AIP 与发送可靠性

- **AIP**：唯一正式协作协议；版本 1.0；字段含 from/to、action、intent、payload、approval_state、correlation_id 等（详见 docs/aip.md）。
- **发送回退（协议库）**：为在千万级调用下降低故障率，`ants.protocol.send` 提供：
  - **SendParams**：`timeout`、`max_retries`、`backoff_base`、`backoff_max`、`backoff_jitter`、可选 `idempotency_key`。
  - **send_aip(base_url, body, params)**（同步）、**async_send_aip(base_url, body, params)**（异步）：对 `POST {base_url}/aip` 做指数退避重试；对 5xx、超时、连接错误重试，对 4xx 不重试。
  - **环境**：`AIP_SEND_TIMEOUT`、`AIP_SEND_MAX_RETRIES` 可覆盖默认（默认 timeout=30，max_retries=4）。
  - 蚁后转发与工人 send_aip 工具均使用该层，保证全球多机房下可配置、可观测、故障率可控。

### 7. 测试/正式环境与运行时配置

- **环境策略**：默认测试；正式环境动作需人类批准；runner 对 write_file/edit_file/run_bash 在参数带 target_env=production 且无 approval_state=approved 时拒绝执行。
- **runtime.yaml**：llm、gitlab、mysql（默认不含 Redis）；敏感值 `${VAR}` 由 env 注入；建员时扁平化注入工人。
- **工人跑容器**：仅蚁后挂载 Docker Socket；工人需起容器时经蚁后代执行（Docker-outside-of-Docker）。

### 8. 留痕与双存储

- **文件库**（volumes/<agent_id> 下 workspace、logs、conversations、aip、todos、reports、context）：供工人构建上下文、拼 prompt；对话与留痕先写文件。
- **数据库**：与文件库双写；LLM token 使用量仅写 DB。Reports 经 append_report 工具双写。
- **工人对进度**：工具 get_colony_status 请求 `GET {ANT_QUEEN_URL}/status?scope=colony`；GitLab 经共享工具与 runtime 配置操作。

### 9. 目录与 Volume

```
ants/
├── ants/          # api, agents, protocol, runtime
├── configs/       # agents/*.yaml, runtime.yaml
├── shared/       # tools, inbox
├── volumes/      # 按 agent_id 的留痕（宿主机）
├── dashboard/    # 独立 SPA + 后端；调蚁后，自连 DB 读 traces
├── docs/         # aip.md, function.md, shorts.md 等
├── Dockerfile
└── pyproject.toml
```

单容器内：/workspace、/logs、/conversations、/aip、/todos、/reports、/context、/shared/tools、/shared/inbox。

---

## II 实现

### 10. 模块

- **ants.api.main**：蚁后 FastAPI；lifespan 建员；/status、/aip（含 user_instruction 拆解）、/instruction；转发使用 protocol.async_send_aip 带重试。
- **ants.runtime.config**：配置目录与 load_agent_config、load_all_agent_configs。
- **ants.runtime.models**：AgentConfig、PromptProfile、EnvironmentPolicy 等。
- **ants.runtime.docker_manager**：DockerSpawner；ensure_volume_dirs、spawn_one、ensure_children；子容器名 ants-<agent_id>，端口 22001。
- **ants.runtime.status**：StatusAggregator；build、build_recursive_status_tree；从留痕与 Docker 聚合状态。
- **ants.runtime.traces**：ensure_trace_dirs、write_log、list_recent_jsonl；留痕路径与双写约定。
- **ants.runtime.runtime_config**：load_runtime_config、runtime_config_to_env、get_llm_api_key（token_ref）。
- **ants.agents.server**：工人 HTTP；POST /aip、GET /status；后台 bootstrap 热加载工具。
- **ants.agents.bootstrap**：加载配置、扫描 /shared/tools、心跳与热加载循环。
- **ants.agents.runner**：加载上下文、调用 LLM 与工具、正式环境校验、压缩过长上下文、写对话与 trace。
- **ants.protocol**：aip（AIPMessage、AIPAction、build_message 等）、status（SingleAntStatus、ColonyStatusDocument 等）、**send**（SendParams、send_aip、async_send_aip）；__version__ = "1.0"。

### 11. 数据流

- 状态：蚁后 /status?scope=colony → StatusAggregator.build；scope=subtree → build_recursive_status_tree。工人 /status 自述或子树。
- 指令：用户 POST /instruction → 蚁后 LLM 拆解 → 多条 assign_task 经 async_send_aip 转发工人。
- 建员：lifespan 中 ensure_children(除根外全部 config)；或 POST /internal/spawn 单员创建。

### 12. 环境变量

| 类别 | 变量 | 说明 |
|------|------|------|
| 配置 | ANTS_CONFIG_DIR, ANT_CONFIG | 配置目录与当前进程 config |
| 留痕 | ANT_BASE_DIR, ANTS_VOLUMES_ROOT | 单 ant 根与 volume 根 |
| 建员 | ANTS_HOST_PROJECT_ROOT, ANTS_IMAGE, ANTS_NETWORK, ANTS_AUTO_SPAWN_DEFAULT | Docker 与自动建员 |
| 鉴权 | ANT_ADMIN_TOKEN / ANTS_ADMIN_TOKEN | 内部接口 X-Admin-Token |
| AIP 发送 | AIP_SEND_TIMEOUT, AIP_SEND_MAX_RETRIES | 可选；发送超时与重试次数 |

runtime.yaml 通过 runtime_config_to_env 注入 LLM_*、GITLAB_*、MYSQL_* 等；token_ref 与 llm.api_keys 见 §7/§10。

### 13. Docker 与扩展

- **docker-compose**：queen 服务；宿主机路径 ANTS_HOST_PROJECT_ROOT；仅 queen 挂载 docker.sock；ANTS_NETWORK 使蚁后访问工人。
- **扩岗**：configs/agents/ 新增 YAML；/internal/spawn 按需建员。
- **工具热加载**：宿主机改 shared/tools 后工人轮询加载，无需重启。

### 14. 风险与建议

- Docker Socket 权限大，上线可换受控代理。
- 留痕须完整，否则排障困难。
- 岗位与能力基于配置，不写死业务逻辑。

---

本文档为 DESIGN 与 原 function 合二为一后的唯一版本；细节协议见 docs/aip.md，短板与待办见 docs/shorts.md。
