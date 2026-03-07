# Changelog

---

2026-03-07 - 协议库日志保持纯净：仅保留 body 内 aip_id 一个 id；trace_id、demand_id 等一律由调用方通过 log_extra 传入。蚁后与 send_aip 工具改为传 log_extra 并设置 body.aip_id。

2026-03-07 - Trace 全链路与可融合日志：协议库 send 增加 log_extra=、logger= 参数；蚁后 user_instruction 入口生成 trace_id/demand_id 并写入所有 forward_msg 与 payload；工人 runner 调用 send_aip 工具前注入 trace_id/correlation_id/demand_id，send_aip 工具将 trace 字段提升到 body 并传 log_extra。一条 trace_id 可查全链，demand_id 便于按需求看卡在哪一步。

2026-03-07 - AIP 协议库日志与链路追踪：ants.protocol.send 使用 logging，可选 AIP_PROTOCOL_LOG/ANTS_PROTOCOL_LOG=1 开启；每条日志带 trace_id/correlation_id/message_id，便于按 trace_id 查整链。function.md §6 与 env 表已更新。

2026-03-07 - LLM usage 落库：payload 增加 agent_id、request_duration_ms、ttft_ms（占位）、turn；function.md 约定 llm_usage 负载。协议库：新增 send_aip_batch（同步并行），模块 doc 标明 Public API（单条/批量）。

2026-03-07 - P0 三项：list_recent_jsonl 改为大文件尾读 O(limit)（小文件仍整读）；GET /status?scope=colony 增加 TTL 缓存（ANTS_STATUS_CACHE_TTL_SEC，默认 5s）；指令拆解后通过 protocol.async_send_aip_batch 并行下发，拆解 LLM 超时可配（ANTS_DECOMPOSE_LLM_TIMEOUT）。function.md 与 shorts.md 已更新。

---

2026-03-07 21:00 - AIP 发送回退：protocol.send 提供 SendParams、send_aip、async_send_aip（指数退避重试），蚁后 _forward_aip 与 shared/tools/send_aip 改用协议库；AIP_SEND_TIMEOUT、AIP_SEND_MAX_RETRIES 可配。DESIGN 与 function 合二为一为 function.md，design.md/DESIGN.md 仅作跳转。

---

2026-03-07 20:18 - Shorts 补齐与 Changelog 规范实施：用户指令拆解（蚁后 LLM 多路下发）、正式环境审批硬性拦截（runner 校验 target_env=production）、token_ref 多 Key（runtime api_keys + runner 按 agent 选 key）、Dashboard 未连 DB 时返回 db_configured 并前端提示、append_report 工具与 Reports 双写、AIP 协议版本 1.0 与 protocol __version__、shorts.md 已补齐项更新；changelog 采用系统时间单条总结。
