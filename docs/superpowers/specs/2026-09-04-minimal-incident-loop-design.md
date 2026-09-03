# 最小 Incident 闭环设计

## 1. 目标与范围

第一轮交付一个可以从空环境启动、无需外部凭证、可自动测试的真实业务闭环：Alertmanager 客户端提交告警，API 校验请求并按稳定指纹去重，创建或复用 Incident，调用方随后可以查询 Incident 与时间线。

本轮同时建立后续模块共同使用的工程基线：Python 3.12、FastAPI application factory、Pydantic Settings、结构化错误、依赖健康探针、SQLAlchemy 仓储端口、pytest、Ruff 和 MyPy。

本轮不接入 LangGraph、LLM、Prometheus、Loki、Tempo、Kubernetes、Celery 或真实审批。它们将在已有 Incident 和仓储契约上逐环增加，避免外部配置阻断第一个闭环。

## 2. 运行模式

应用支持三种环境：`test`、`development`、`production`。

- `test` 默认使用 SQLite 内存数据库和 Fake 依赖探针。
- `development` 默认使用本地 SQLite 文件；显式提供 PostgreSQL URL 时可切换数据库。Redis 在本轮只是可注入 readiness 探针，不承担业务状态。
- `production` 必须提供 PostgreSQL URL、Redis URL 和 Alertmanager 共享密钥；缺失任一配置时应用启动失败。生产环境永不注册 `/v1/lab` 路由。

`.env.example` 只包含无敏感信息的可运行开发默认值。未来 LLM 和 Kubernetes 配置均设计成可选：未配置时使用确定性 Fake 或禁用对应能力，不影响已有 API 启动。

## 3. 模块边界

### `shared`

- `config.py` 定义 `Settings`，负责环境变量解析与跨字段约束。
- `database.py` 创建 SQLAlchemy engine/session，并提供建表与健康探针。
- `health.py` 定义 `DependencyProbe` 协议及探针聚合逻辑。
- `errors.py` 定义 RFC 9457 风格 Problem Details 与异常处理器。

### `incidents`

- `schemas.py` 定义受限 Alertmanager 入站模型和 Incident 出站模型。未知字段允许存在于告警原始载荷，但业务只读取白名单字段。
- `fingerprint.py` 对规范化标签计算 SHA-256。忽略 `startsAt`、`endsAt`、annotations 和 Alertmanager 外层状态，保证同一告警重投具有相同指纹。
- `models.py` 定义 `Incident`、`Alert`、`TimelineEvent`。告警指纹具有唯一约束；Incident 状态使用受限枚举。
- `repository.py` 定义仓储协议与 SQLAlchemy 实现。事务内先插入告警；唯一冲突时查询原 Alert 所属 Incident，从而使重复并发请求保持幂等。
- `service.py` 编排摄入流程，不依赖 FastAPI。
- `router.py` 暴露 HTTP 接口，不包含业务规则。

### `apps/api`

- `main.py` 提供 `create_app(settings, probe, repository) -> FastAPI`，依赖均可注入。
- `/live` 只表示进程能处理请求，始终返回 200。
- `/ready` 聚合数据库和可选 Redis 探针；全部成功返回 200，否则返回 503 Problem Details，并列出失败依赖但不泄露连接串。

## 4. API 契约

### `POST /v1/alerts/alertmanager`

开发和测试环境允许通过设置显式关闭签名校验。启用时，请求必须携带：

- `X-AIOps-Timestamp`：Unix 秒，和服务端时钟相差不得超过 300 秒。
- `X-AIOps-Signature`：`v1=<hex>`，内容为 `HMAC-SHA256(secret, timestamp + "." + raw_body)`。

请求最大 1 MiB；`alerts` 必须包含 1 到 100 项。每条告警必须有 `alertname`、`service`、`environment` 标签以及 RFC 3339 `startsAt`。

成功返回 `202 Accepted`：

```json
{
  "incident_ids": ["uuid"],
  "created_incident_ids": ["uuid"],
  "duplicate_alerts": 0
}
```

同一批告警按 `environment + service` 分组，每组建立一个 Incident。同一指纹的重投返回原 Incident ID 并增加 `duplicate_alerts`，不新增 Incident、Alert 或时间线事件。本轮不做跨服务拓扑聚合；它属于下一轮，并将在不改变摄入接口的前提下扩展。

### `GET /v1/incidents/{incident_id}`

返回 Incident 基本字段、关联告警摘要和按发生时间升序排列的时间线。不存在时返回 `404` Problem Details；UUID 格式错误返回 `422`。

### 健康检查

- `GET /live` 返回 `{"status":"ok"}`。
- `GET /ready` 成功返回 `{"status":"ready","dependencies":{"database":"ok","redis":"ok|disabled"}}`。
- 失败返回 503，`type` 为稳定错误 URI，`extensions.dependencies` 保存 `unavailable` 状态。

## 5. 数据与状态

`Incident` 初始状态为 `open`，保存 UUID、environment、primary service、severity、first_seen、last_seen、version 和创建时间。

`Alert` 保存 UUID、唯一 fingerprint、incident_id、规范化标签、白名单 annotations、starts_at、ends_at、原始外部 generator URL 和创建时间。原始请求不整体持久化，避免秘密或无限字段进入数据库。

`TimelineEvent` 保存 UUID、incident_id、事件类型、occurred_at 和结构化 payload。本轮只生成 `incident_created` 和 `alert_received`；重复请求不生成事件。

事务边界为单个 Alert：同一 HTTP 批次允许部分告警映射到既有 Incident，但任何模型校验失败会在进入 service 前拒绝整个请求。数据库异常会回滚当前请求并返回 503，不向客户端声称已接受。

## 6. 错误与安全

- 所有预期错误使用 `application/problem+json`，包括稳定 `type`、`title`、HTTP `status`、`detail`、实例路径和 `trace_id`。
- 签名比较使用常量时间函数；时间戳过期、签名缺失或错误统一返回 401，避免泄露验证细节。
- 日志不得输出共享密钥、连接串或完整告警 annotations。
- 数据库唯一约束是幂等性的最终防线，进程内锁不作为正确性依赖。
- 请求体、告警数量、标签数量、标签键值长度均有限制；超限返回 413 或 422。

## 7. 测试与验证

实现严格遵循 RED-GREEN-REFACTOR，每一类行为先看到预期失败：

1. Settings 测试覆盖开发默认值、生产缺配置拒绝、生产禁用 lab。
2. 应用测试覆盖 live、ready 成功、探针失败时 503 和 Problem Details。
3. 签名测试覆盖正确签名、错误签名、过期时间戳及开发关闭验证。
4. 指纹测试覆盖标签顺序无关、时间字段变化不改变指纹、核心标签变化产生新指纹。
5. 摄入集成测试覆盖首次创建、重复重投、同批分组、无效载荷和事务回滚。
6. 查询测试覆盖事件与时间线排序、404 和 UUID 校验。
7. 最终运行 `pytest`、`ruff check .`、`ruff format --check .`、`mypy src apps`，再用本地开发配置启动 Uvicorn 并执行 HTTP 冒烟测试。

SQLite 用于快速测试和无依赖开发；PostgreSQL 是生产目标。涉及唯一冲突、JSON 和并发语义的测试将标记为 PostgreSQL 集成测试，在 Compose 可用时运行，默认单元套件不得因 Docker 未安装而失败。

## 8. 后续演进

下一轮增加拓扑快照和时间窗聚合，但保留现有 Alert 指纹和摄入响应。之后实现四类 Fake Investigator，以结构化 Evidence 跑通并行调查；真实遥测适配器、LangGraph checkpoint、受控执行器和故障实验逐轮替换 Fake。任何外部能力未配置时均返回明确 `disabled` 或 `missing_source`，不得伪造事实。
