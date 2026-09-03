# 模块拆分与接口边界

## 1. 依赖规则

```text
incident API -> application services -> ports <- telemetry/kubernetes adapters
                                  -> LangGraph coordinator
investigators -> read-only query ports
runbook planner -> registry/policy -> isolated executor -> restricted K8s client
reasoning modules -X-> concrete telemetry SDK or Kubernetes write client
```

- 调查器不能依赖执行器，避免读路径升级为写权限。
- 所有数据源适配器输出统一 Evidence，不把供应商响应传入 LLM。
- 执行器只消费已注册的 `RunbookExecutionCommand`，不消费自然语言。
- 恢复验证器读取新遥测窗口，不复用执行前快照。

## 2. 模块清单

| 模块 | 职责 | 输入 | 输出 | 测试重点 |
|------|------|------|------|----------|
| `incidents` | Webhook、去重、聚合、状态机 | 告警 | Incident/Timeline | 重复、乱序、关联窗口 |
| `topology` | 服务依赖、owner、环境 | service id | topology snapshot | 环、缺失节点、版本 |
| `investigators` | 分数据源调查 | InvestigationTask | Evidence[] | 查询限制、部分失败 |
| `reasoning` | 证据归并、假设、排序 | Evidence[] | Hypothesis[] | 反证、引用、预算 |
| `runbooks` | 注册、策略、审批、执行 | ActionProposal | ExecutionResult | RBAC、幂等、资源版本 |
| `verification` | 稳定窗口与恢复判定 | policy、fresh telemetry | VerificationResult | 波动、超时、不确定 |
| `reports` | 时间线、摘要、复盘 | incident state | Markdown/JSON | 事实引用、脱敏 |
| `observability` | Agent 自监控与审计 | node/tool events | spans/metrics/audit | 高基数和 Secret |
| `lab` | 微服务与故障注入 | scenario command | ground truth/run id | 可重复、自动清理 |

## 3. 核心端口

### 调查任务和查询端口

```python
class InvestigationTask(BaseModel):
    task_id: UUID
    source_type: Literal["metric", "log", "trace", "change"]
    service: str
    template_id: str
    parameters: dict[str, str | int | float]
    window: TimeWindow
    hypothesis_ids: list[UUID]

class Investigator(Protocol):
    async def investigate(self, task: InvestigationTask) -> list[Evidence]: ...
```

`template_id` 必须存在于代码注册表；参数由 Pydantic discriminated union 校验。适配器负责超时、结果上限、重试和脱敏。

### 根因模型

```python
class Hypothesis(BaseModel):
    hypothesis_id: UUID
    summary: str
    affected_component: str
    supporting_evidence_ids: list[UUID]
    contradicting_evidence_ids: list[UUID]
    confidence: float
    next_questions: list[str]
```

如果 supporting evidence 为空，候选项只能作为待调查假设，不能标记为最终根因。最终 Top-1 必须达到阈值且满足最小数据源策略。

### Runbook 端口

```python
class RunbookExecutionCommand(BaseModel):
    incident_id: UUID
    runbook_name: str
    runbook_version: str
    environment: str
    parameters: dict[str, str | int]
    target_resource_uid: str
    approval_id: UUID | None
    idempotency_key: str

class RunbookExecutor(Protocol):
    async def dry_run(self, command: RunbookExecutionCommand) -> PolicyResult: ...
    async def execute(self, command: RunbookExecutionCommand) -> ExecutionResult: ...
```

## 4. Incident 状态机

```text
open -> investigating -> awaiting_approval -> remediating -> verifying -> resolved
                        |                    |              |
                        +-> handed_off <-----+--------------+
```

- 所有迁移使用版本号做乐观锁。
- `resolved` 必须关联 successful VerificationResult。
- `awaiting_approval` 恢复时必须重新执行策略检查。
- `handed_off` 保留当前调查状态，人工可重新开启调查。

## 5. 工具白名单

| 数据源 | 首版模板 |
|--------|----------|
| Prometheus | 服务请求率/错误率/P95、容器 CPU/内存、Redis pool 指标、DB duration |
| Loki | 错误签名计数、指定 trace id 日志、服务代表性错误样例 |
| Tempo | 错误 Trace 搜索、关键 Span 延迟分解、服务依赖传播 |
| Kubernetes | Deployment/Pod/Event、rollout history、resource status |
| Change | 最近镜像版本、ConfigMap 哈希、部署时间线 |

Agent 只选择模板和参数。新增模板需要代码评审、成本上限和 Fixture 测试。

## 6. API 边界

| 方法与路径 | 用途 | 权限 |
|------------|------|------|
| `POST /v1/alerts/alertmanager` | 接收签名 Webhook | alertmanager service |
| `GET /v1/incidents/{id}` | 事件、证据和时间线 | oncall |
| `GET /v1/incidents/{id}/events` | SSE 调查进度 | oncall |
| `POST /v1/incidents/{id}/actions` | 提议注册 Runbook | commander |
| `POST /v1/approvals/{id}/decision` | 审批动作 | approver |
| `POST /v1/lab/scenarios/{name}/inject` | 注入实验故障 | lab_admin，仅 lab |
| `POST /v1/evaluations/runs` | 执行固定场景评测 | platform_admin |

生产配置中不注册 `/lab` 路由，且 API 进程不持有 Kubernetes 写凭证。

## 7. 审计事件

关键事件包括 alert_received、incident_merged、query_executed、evidence_added、hypothesis_ranked、action_proposed、approval_decided、runbook_executed、verification_completed 和 incident_resolved。审计记录保存 actor、时间、输入哈希、结果摘要和 trace id，不保存 Secret 或无限原始日志。
