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
  - **send_aip_batch(requests, params)**（同步）、**async_send_aip_batch(requests, params)**（异步）：多路并行发送，每条仍走上述重试/退避；蚁后指令拆解后批量下发使用异步接口；同步场景可用 send_aip_batch。
  - **环境**：`AIP_SEND_TIMEOUT`、`AIP_SEND_MAX_RETRIES` 可覆盖默认（默认 timeout=30，max_retries=4）。
  - **日志**：标准库 `logging`，logger 名为 `ants.protocol.send`。库内仅保留一个 id 字段 **aip_id**（从 body 读取）；设 `AIP_PROTOCOL_LOG=1` 可开启 INFO。传 `logger=` 接入项目 logger，传 `log_extra=` 注入 trace_id、demand_id 等，由调用方（如 Ants）在 log_extra 中传入以便整链追踪。
  - 蚁后转发与工人 send_aip 工具均使用该层，保证全球多机房下可配置、可观测、故障率可控。

### 7. 测试/正式环境与运行时配置

- **环境策略**：默认测试；正式环境动作需人类批准；runner 对 write_file/edit_file/run_bash 在参数带 target_env=production 且无 approval_state=approved 时拒绝执行。
- **config.json**：llm、gitlab、mysql、minio、ants 等统一配置；字面默认值，Docker Compose 内零配置自动连通；建员时仅 llm/mysql/gitlab 扁平化注入工人。
- **工人跑容器**：仅蚁后挂载 Docker Socket；工人需起容器时经蚁后代执行（Docker-outside-of-Docker）。

### 8. 留痕与双存储

- **跟踪日志**：`ants.runtime.trace_log` 在 ANTS_TRACE_LOG=1 时向 logger `ants.trace` 打一行式事件（event + trace_id、agent_id、ts 等）；每条 extra 含 ts（ISO UTC）便于 Grafana 按时间查。Queen 打 user_instruction/delegate、Worker 打 assign_task、Runner 打 run_task_start/run_task_done、llm_call、tool_call；调用 AIP 发送时通过 log_extra 传入 trace_id、agent_id，与协议层 aip_id 一起构成整链可查。
- **agent_id 约定**：所有留痕（trace_log、write_log、write_trace、conversation、aip）均带 agent_id，值为配置中的 agent 名称（如 creator_decider、backend），非 UUID，便于按「谁」过滤。
- **文件库**（volumes/<agent_id> 下 workspace、logs、conversations、aip、todos、reports、context）：供工人构建上下文、拼 prompt；对话与留痕先写文件；JSONL 与落库统一使用 UTF-8（ensure_ascii=False / utf8mb4）。
- **数据库**：与文件库双写；建库/建表自动使用 utf8mb4；write_trace 时 payload 内自动注入 agent_id。LLM token 使用量仅写 DB（trace_type=llm_usage）。Reports 经 append_report 工具双写。
- **llm_usage 负载约定**：payload 含 ts（ISO）、agent_id（工人）、model、prompt_tokens/completion_tokens/total_tokens、request_duration_ms（整次调用耗时）、ttft_ms（首 token 延迟，流式时填写、否则 null）、turn（当轮对话序号）。
- **工人对进度**：工具 get_colony_status 请求 `GET {ANT_QUEEN_URL}/status?scope=colony`；GitLab 经共享工具与 runtime 配置操作。

### 9. 目录与 Volume

```
ants/
├── ants/          # api, agents, protocol, runtime
├── configs/       # config.json（统一配置：llm/mysql/minio/gitlab/ants）, agents/*.json（拓扑与能力）
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
- **ants.runtime.traces**：ensure_trace_dirs、write_log（每行带 agent_id）、list_recent_jsonl（大文件尾读 O(limit)）；append_jsonl 使用 UTF-8；留痕路径与双写约定。
- **ants.runtime.trace_log**：trace_log(event, trace_id=…, **kwargs)；extra 内自动带 ts（ISO UTC）；调用方应传 agent_id。ANTS_TRACE_LOG=1 时向 ants.trace 打一行式事件，供 Grafana 按 trace_id/agent_id/时间查。
- **ants.runtime.runtime_config**：load_runtime_config、runtime_config_to_env、get_llm_api_key（token_ref）。
- **ants.runtime.db**：可选 MySQL 双写；无库时自动建库（utf8mb4）、建表（utf8mb4）；write_trace 时 payload 内注入 agent_id，JSON 使用 UTF-8。
- **ants.agents.server**：工人 HTTP；POST /aip、GET /status；后台 bootstrap 热加载工具。
- **ants.agents.bootstrap**：加载配置、扫描 /shared/tools、心跳与热加载循环。
- **ants.agents.runner**：加载上下文、调用 LLM 与工具（打 trace_log llm_call/tool_call 带 agent_id）、正式环境校验、压缩过长上下文、写对话与 trace（conversation 行带 agent_id）。
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
| AIP 协议日志 | AIP_PROTOCOL_LOG, ANTS_PROTOCOL_LOG | 可选；设为 1/true/yes 开启 protocol send 的 INFO 日志，便于按 trace_id 查链路 |
| 跟踪日志 | ANTS_TRACE_LOG | 可选；设为 1/true/yes 开启 ants.trace 结构化日志（user_instruction、delegate、assign_task、run_task_start/run_task_done 等），每行含 trace_id、agent_id、ts（ISO），便于 Grafana 按链路/角色/时间查 |
| 状态 | ANTS_STATUS_CACHE_TTL_SEC | 可选；colony status 缓存 TTL（秒），默认 5，0 禁用 |
| 拆解 | ANTS_DECOMPOSE_LLM_TIMEOUT | 可选；指令拆解 LLM 调用超时（秒），默认 60 |

config.json 通过 runtime_config_to_env 将 llm/mysql/gitlab 注入为 LLM_*、MYSQL_*、GITLAB_* 等；token_ref 与 llm.api_keys 见 §7/§10。

### 13. Docker 与扩展

- **docker-compose**：queen 服务；宿主机路径 ANTS_HOST_PROJECT_ROOT；仅 queen 挂载 docker.sock；ANTS_NETWORK 使蚁后访问工人。
- **扩岗**：configs/agents/ 新增 JSON；/internal/spawn 按需建员。
- **工具热加载**：宿主机改 shared/tools 后工人轮询加载，无需重启。

### 14. 风险与建议

- Docker Socket 权限大，上线可换受控代理。
- 留痕须完整，否则排障困难。
- 岗位与能力基于配置，不写死业务逻辑。

---

本文档为 DESIGN 与 原 function 合二为一后的唯一版本；细节协议见 docs/aip.md，短板与待办见 docs/shorts.md。
