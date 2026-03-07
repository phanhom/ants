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

- **贯穿标识**：已实现 trace_id 全链（Queen → Worker → Runner、AIP log_extra）；agent_id、ts 已打入 trace 与落库。可选增强：request_id、多级 correlation 以兼容外部系统。
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

**已完成（P0 三项）**：JSONL 尾读 O(limit)、状态聚合 TTL 缓存、指令拆解并行下发 + 拆解/发送超时可配置（协议层 `async_send_aip_batch`）。**可观测**：trace_id 全链、agent_id/ts 打入 trace 与 DB，AIP 库仅 aip_id + log_extra 融合。

---

## 走向顶级 / 全球可用还差什么（严格评估）

以下按「AIP 协议库」与「Ants 应用」分开，若要变成全球可用的顶级方案，仍缺的关键项。

### AIP 协议库（ants.protocol）

| 缺口 | 说明 |
|------|------|
| **独立包与版本** | 仍在 ants 仓库内，无独立 pip 包（如 `ants-aip` / `aip-protocol`）；无语义化版本与 CHANGELOG，下游无法锁版、无法独立升级协议层。 |
| **契约与多语言** | 无正式 OpenAPI/AsyncAPI 或 .proto 描述，非 Python 生态无法生成客户端；无「最小请求/响应」的机器可读 schema，第三方集成成本高。 |
| **传输与认证抽象** | 当前写死 HTTP POST + JSON；无传输层抽象（如 gRPC、WebSocket、队列占位），无认证钩子（Bearer、mTLS、自定义 header），企业/跨域部署受限。 |
| **可观测与依赖** | 已支持 logger=、log_extra=、aip_id，足够融合日志；缺：无 OpenTelemetry 等标准 span 注入、无可选 metrics 回调，与现有 APM 体系集成需自行接。 |
| **文档与示例** | 无独立「协议库 README」、无「5 分钟发一条 AIP」的复制粘贴示例、无与框架无关的最小客户端代码，不利于「任何人拿过去就能用」。 |

### Ants 应用（多智能体运行时）

| 缺口 | 说明 |
|------|------|
| **安全与合规** | /instruction 无鉴权；工人持蚁后 URL，攻击面大；无审计日志、无敏感操作二次确认，难以满足企业合规。 |
| **韧性与 SLA** | 蚁后转发 503 即抛，无重试；无熔断、无限流、无降级策略；拆解失败仅回退到「发第一工人」，无部分成功、无重试队列。 |
| **多租户与规模** | 单 colony 单拓扑，无租户/命名空间隔离；状态缓存单实例、无分布式缓存；无法「一个平台多团队、多项目」规模化。 |
| **协议演进** | AIP 版本 1.0 写死，无版本协商、无向后兼容策略，未来扩展 action 或字段易破坏现有客户端。 |
| **测试与发布** | 无自动化测试、无 CI 契约测试、无发布清单，回归与升级风险高，难以对外承诺稳定性。 |

### 小结：顶级还差什么

- **协议库**：独立包 + 语义化版本 + 契约（OpenAPI/IDL）+ 传输/认证可插拔 + 多语言示例与文档。
- **应用**：鉴权/审计、转发重试与熔断、多租户或命名空间、协议版本策略、自动化测试与发布流程。
