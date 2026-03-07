# Ants 短板与待办（Shorts）

对照 DESIGN 与当前实现：仍缺或偏弱的部分，以及近期已补齐项。批判性评估，便于排优先级。

---

## 已补齐（近期）

- **LLM token 使用**：runner 每轮 `chat.completions.create` 返回后取 `usage`，`write_trace(agent_id, "llm_usage", payload)` 仅写 DB，不写文件库。
- **工人对进度**：共享工具 `get_colony_status` 请求 `GET {ANT_QUEEN_URL}/status?scope=colony`，各岗位已加入 `tools_allowed`。
- **GitLab 操作**：6 个共享工具（list_projects、get_file、create_branch、create_merge_request、trigger_pipeline、pipeline_status），backend/creator_decider 等已配置；skill `gitlab_ops` 已加。
- **Todo 双写**：`append_todo` 写文件后调用 `write_trace(agent_id, "todo", row)`，文件库与 DB 双写。
- **文件库/DB 分工**：在 function.md §2.10 已说明：文件库双写 DB；token 使用仅写 DB；对进度与 GitLab 工具。
- **用户指令拆解**：蚁后收到 `user_instruction` 后调用 LLM 按工人 role/skills 拆解为多条 assign_task 多路下发；失败时回退为转发给第一工人。
- **正式环境审批硬性拦截**：runner 对 write_file、edit_file、run_bash 在参数带 target_env=production 且未 approval_state=approved 时拒绝执行。
- **token_ref 多 Key**：runtime 支持 llm.api_keys 映射；runner 按 agent 的 token_ref 选择 api_key。
- **Dashboard 未连 DB 提示**：后端 /api/traces 在未配置或连不上 MySQL 时返回 db_configured: false 与 message；前端 Traces 页展示醒目提示。
- **Reports 双写**：`append_report` 工具写 reports/reports.jsonl 并 write_trace(agent_id, "report", row)；各岗位已加入 tools_allowed。
- **协议版本 1.0**：docs/aip.md §10 与 ants.protocol.__version__ 一致；兼容性承诺已写。

---

## 仍可增强

### 蚁后拆解与工人执行分工

**设计**：蚁后只做接收、拆解、下发；工人做执行（LLM + 工具）。蚁后侧拆解已用 LLM，与工人共用 runtime llm 配置；工人不建员、不拆解，职责清晰。

### 跨机与生产就绪

- **跨机**：AIP 支持 to_base_url，协议和转发已有；实际多机房部署时还需各节点网络/网关/鉴权（设计已留扩展口）。
- **协议库**：`ants.protocol` 已独立，可单独打包；后续可加强文档与示例便于第三方集成。

---

## 小结

当前主干（AIP、双接口、状态递归、指令拆解、工人 LLM+工具、双写留痕、token 落库、对进度、GitLab 工具、正式环境拦截、token_ref、Dashboard+DB 提示、append_report、协议 1.0、热加载）已搭好。后续以跨机部署、协议库推广与运维体验为主。
