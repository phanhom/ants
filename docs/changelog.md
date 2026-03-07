# Changelog

---

2026-03-07 21:00 - AIP 发送回退：protocol.send 提供 SendParams、send_aip、async_send_aip（指数退避重试），蚁后 _forward_aip 与 shared/tools/send_aip 改用协议库；AIP_SEND_TIMEOUT、AIP_SEND_MAX_RETRIES 可配。DESIGN 与 function 合二为一为 function.md，design.md/DESIGN.md 仅作跳转。

---

2026-03-07 20:18 - Shorts 补齐与 Changelog 规范实施：用户指令拆解（蚁后 LLM 多路下发）、正式环境审批硬性拦截（runner 校验 target_env=production）、token_ref 多 Key（runtime api_keys + runner 按 agent 选 key）、Dashboard 未连 DB 时返回 db_configured 并前端提示、append_report 工具与 Reports 双写、AIP 协议版本 1.0 与 protocol __version__、shorts.md 已补齐项更新；changelog 采用系统时间单条总结。
