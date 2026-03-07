# Ants 短板与待办（Shorts）

严格评判：当前仍做得不好或缺失的部分，便于排优先级。已实现的能力写在 [function.md](function.md)，此处不列。

---

## 1. 指令拆解质量与延迟

- **串行下发**：已解决；拆解后通过协议层 `async_send_aip_batch` 并行下发，首轮延迟不再随工人数线性增长。
- **拆解依赖 LLM**：prompt 简单（一段 system + 工人列表 + instruction），无 few-shot、无输出 schema 校验，拆错或漏拆时只能回退到「发第一工人」，无部分成功或重试策略。
- **无幂等与去重**：同一 instruction 多次提交会多次拆解、多次下发，无 task_id / idempotency key 去重。

---

## 2. 算法与数据结构的硬伤

- **list_recent_jsonl 大文件 O(n)**：已改为小文件整读、大文件从尾按块 seek 读取，保证 O(limit) 时间与空间。
- **状态聚合无缓存**：已对 `GET /status?scope=colony` 做短期 TTL 缓存（`ANTS_STATUS_CACHE_TTL_SEC`，默认 5s，0 禁用），其余 scope 仍实时计算。

---

## 3. 正式环境保护的脆弱性

- **完全依赖 LLM 传参**：拦截仅当工具参数里显式带 `target_env=production` 或 `target=production`。若模型不传该参数，即使在做生产写操作也无法拦截，仍属「模型自律」。
- **无结构化管理**：没有「正式路径」白名单/黑名单（如某目录、某分支禁止未审批写入），无法做路径级硬约束。

---

## 4. 跨机与韧性

- **无重试**：蚁后 forward AIP 到工人时一次 503 即向上抛，无重试、无退避。
- **超时**：AIP 发送由 `AIP_SEND_TIMEOUT` 可配置；拆解 LLM 由 `ANTS_DECOMPOSE_LLM_TIMEOUT` 可配置（默认 60s）。
- **无统一网关**：跨机房时 to_base_url 靠调用方拼，无统一入口、健康检查与熔断。

---

## 5. 安全与鉴权

- **/instruction 无鉴权**：任何人可向蚁后 POST 指令，无 token、无 IP 白名单。
- **工人握有蚁后 URL**：`ANT_QUEEN_URL` 注入工人后，工人可主动打蚁后；若工人被控，蚁后暴露面大。
- **Dashboard**：后端 /api/traces 无鉴权；MySQL 凭据由 Dashboard 独立配置，与 Ants 分离，部署易漏配或权限过大。

---

## 6. 可观测与运维

- **无贯穿标识**：请求级 request_id / correlation_id 未在 AIP、日志、DB trace 中统一传递，排障时难以串起一条链路。
- **DB**：`trace_events` 表无文档化索引建议（如 agent_id+ts、trace_type+ts），数据量大时查询可能变慢。
- **错误形态**：工具执行失败时 runner 仅把异常转成字符串返回给模型，无结构化错误码或可区分类型。

---

## 7. 协议库与生态

- **未独立打包**：`ants.protocol` 仍在 ants 仓库内，无独立 pip 包、无 `pip install ants-protocol` 文档。
- **无 SDK 示例**：第三方「如何用 AIP 发一条消息、解析 status」的示例或最小客户端缺失，不利于「导出成库给所有人用」。

---

## 8. 测试与质量

- **无自动化测试**：无单测、无集成测、无 API 契约测试，改动依赖人工验证，回归成本高。
- **建议优先覆盖**：协议层（AIPMessage 序列化/反序列化、SendParams.backoff_delay 边界）、`list_recent_jsonl`「只读最后 N 行」语义（临时文件单测）、`build_recursive_status_tree` 给定 topology + statuses 的树结构。

---

## 9. 文档与体验

- **DESIGN 与 function 重叠**：部分内容两处都有，易不同步；缺少「五分钟快速参考」（两接口 + 常用字段一览）。
- **aip.md 过长**：协议文档信息量大，但无「最小可行请求/响应」一页速查。

---

## 10. 代码与实现细节

- **时间与默认值分散**：`utc_now` / `utc_now_iso` 在 aip、models、status、traces 多处定义，应收敛到单一公共模块；`_aip_send_params()` 与 `SendParams` 默认值重复，应以 SendParams + env 为唯一来源。
- **技能与工具耦合**：`SKILL_DESCRIPTIONS` 在 runner 内写死，与 configs/agents 的 skills 易不同步，建议迁出为配置或 skills.yaml；工具发现依赖 `sys.modules` 下 `ants_tools_*`，与 bootstrap 加载顺序强绑定，更稳妥为显式注册表或清单。
- **tenacity 未用**：pyproject 声明 tenacity，重试逻辑为手写循环，要么改用 tenacity 统一退避语义，要么从依赖移除，避免误导。

---

## 小结（优先级建议）

| 优先级 | 方向 | 说明 |
|--------|------|------|
| P0 | JSONL 尾读 O(limit) | list_recent_jsonl 从文件尾按块读，避免大文件 O(n) 与 OOM |
| P0 | 状态聚合缓存/预聚合 | 避免每次 /status 全量扫盘 + Docker，可短期 TTL 或异步预聚合 |
| P0 | 指令拆解并行/可配置 | 降低首轮延迟，可配置超时与重试 |
| P1 | 正式环境路径级约束 | 不单靠 LLM 传参，增加路径/分支白名单或策略 |
| P1 | /instruction 鉴权 | 至少可选 token 或 IP 限制 |
| P2 | 贯穿 request_id | 便于日志与 trace 串联 |
| P2 | 协议独立包 + 最小示例 | 兑现「可导出成库」 |
| P2 | 自动化测试 | 单测 + 关键路径集成测（协议、list_recent_jsonl、build_recursive_status_tree） |
| P3 | Dashboard 鉴权与 DB 索引文档 | 安全与性能可运维 |
| P3 | 时间/默认值收敛、技能配置化 | 可维护性与一致性 |

**已完成（P0 三项）**：JSONL 尾读 O(limit)、状态聚合 TTL 缓存、指令拆解并行下发 + 拆解/发送超时可配置（协议层 `async_send_aip_batch`）。
