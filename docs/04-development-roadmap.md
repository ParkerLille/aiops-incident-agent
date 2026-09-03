# AIOps Incident Agent Implementation Plan

> **For agentic workers:** 实施时必须使用 TDD；每个阶段单独评审、测试并提交。当前目录尚未初始化 Git，开始编码前先为本工程初始化独立仓库。

**Goal:** 在自建可观测微服务环境中，交付能够归并告警、并行调查、证据化定位根因并安全执行 Runbook 的可恢复 AIOps Agent。

**Architecture:** Incident API 和 LangGraph Coordinator 管理事件状态；四类 Investigator 通过白名单只读工具并行生成 Evidence；独立 Runbook Executor 使用受限 Kubernetes 凭证执行类型化动作；Verification 使用新遥测窗口确定是否恢复。

**Tech Stack:** Python 3.12、FastAPI、LangGraph、PostgreSQL、Redis、Celery、OpenTelemetry、Prometheus、Loki、Tempo、Grafana、Kubernetes/kind、Pytest、Docker Compose。

## 全局约束

- 只支持三个固定故障、四类只读调查源和三个注册 Runbook。
- 禁止任意 Shell、任意遥测查询和任意 Kubernetes Patch。
- LLM 不授予权限、不批准动作、不直接判断恢复成功。
- 调查和执行使用不同身份；查询、时间、轮数、Token 和费用都有上限。
- 简历数字只来自版本化实验报告，并标注自建环境。

---

## 阶段 1：工程基线与事件 API

**创建文件：** `pyproject.toml`、`.env.example`、`compose.yaml`、`apps/api/main.py`、`src/incident_agent/shared/{config,db}.py`、`tests/smoke/test_health.py`。

**交付接口：** `create_app(settings)->FastAPI`、live/ready 健康检查和统一 Problem Details 错误。

1. 先写配置、live/ready 和生产禁用 lab route 的失败测试。
2. 建立 Pydantic Settings、application factory、PostgreSQL/Redis 依赖探针。
3. 配置 Ruff、MyPy、Pytest、Alembic 与 JSON 日志。
4. 使用 Compose 从空环境启动，验证依赖断开时 ready=503。
5. 提交 `chore: establish incident agent service baseline`。

## 阶段 2：告警去重、聚合与事件状态机

**创建文件：** `src/incident_agent/incidents/{models,schemas,fingerprint,aggregation,service,router}.py`、`tests/integration/incidents/test_alert_aggregation.py`。

**交付接口：** `AlertIngestService.ingest(payload)->IncidentRef`；重复 Webhook 返回同一事件。

1. 写重复、乱序、同服务不同错误和依赖服务相关告警的测试。
2. 实现 Alert、Incident、TimelineEvent 模型和唯一指纹约束。
3. 实现基于标签规范化、时间窗口和拓扑邻接的聚合规则。
4. 对 Alertmanager Webhook 做签名、Schema、大小和频率限制。
5. 运行并发重复投递测试，确认只创建一个 Incident。
6. 提交 `feat: aggregate alerts into durable incidents`。

## 阶段 3：可观测实验环境

**创建文件：** `lab/services/{gateway,order,inventory,payment}/`、`lab/scenarios/*.yaml`、`infra/kind/cluster.yaml`、`infra/otel/collector.yaml`、`tests/lab/test_scenarios.py`。

**交付接口：** `make lab-up`、`make inject SCENARIO=db-slow-query`、`make lab-reset` 等价命令。

1. 写场景 smoke test：健康基线、注入后告警、reset 后恢复。
2. 实现四个最小微服务和可重复流量生成器，统一 OTel trace context。
3. 部署 Prometheus、Loki、Tempo、Grafana 和 Alertmanager。
4. 实现慢查询、Redis pool 耗尽、Payment 错误配置三个显式开关。
5. 为每个 run 保存 ground truth、开始/结束时间、影响服务和期望证据。
6. 连续运行每个场景三次，确认告警与证据稳定。
7. 提交 `feat: add observable incident simulation lab`。

## 阶段 4：服务拓扑与只读工具

**创建文件：** `src/incident_agent/topology/`、`src/incident_agent/investigators/tools/{prometheus,loki,tempo,kubernetes,changes}.py`、`tests/contract/tools/`。

**交付接口：** 类型化 QueryTemplate Registry 和 `execute(template_id, parameters, window)`。

1. 对未知模板、非法服务、超长窗口、超量日志和超时写失败测试。
2. 建立服务目录、依赖边、owner 与环境模型，事件创建时冻结 topology snapshot。
3. 实现 Prometheus/Loki/Tempo/Kubernetes/Change 只读适配器。
4. 工具层强制 30 分钟窗口、返回上限、Secret 脱敏和 trace propagation。
5. 使用真实实验栈执行契约测试，验证每个模板的字段和单位。
6. 提交 `feat: add bounded telemetry investigation tools`。

## 阶段 5：Evidence 与四类 Investigator

**创建文件：** `src/incident_agent/investigators/{models,base,metrics,logs,traces,changes}.py`、`tests/unit/investigators/`、`tests/fixtures/telemetry/`。

**交付接口：** `Investigator.investigate(task)->list[Evidence]`；Evidence ID 可确定性重建。

1. 用固定 Fixture 写正常、异常、无数据、部分源失败和重复执行测试。
2. 实现 InvestigationTask discriminated union 与 Evidence 校验。
3. 每个 Investigator 只能访问自己的端口，并把单位、时间窗和来源规范化。
4. 对日志先聚类计数再取代表样例，避免把整段日志发送给模型。
5. 实现 `merge_evidence_by_id` reducer，验证并行重试不重复证据。
6. 提交 `feat: produce normalized multi-source evidence`。

## 阶段 6：协调图、假设与有限调查循环

**创建文件：** `src/incident_agent/reasoning/{state,graph,planner,hypotheses,scoring}.py`、`tests/integration/reasoning/test_investigation_graph.py`。

**交付接口：** `compile_incident_graph(checkpointer)`；Hypothesis 必须引用支持/反证 Evidence ID。

1. 用 Fake Investigator 写并行 fan-out、部分失败、冲突证据、轮数与 Token 预算测试。
2. 实现 topology/context 加载和受限结构化调查计划。
3. 使用 LangGraph Send/并行分支派发任务，以 reducer 合并 Evidence。
4. 实现候选根因结构化输出和确定性分数校准；无支持证据不能成为 final RCA。
5. 证据不足时只允许一次定向调查；预算耗尽生成 handoff 包。
6. 接入 PostgreSQL Checkpointer 并测试 Worker 重启恢复。
7. 提交 `feat: orchestrate bounded evidence-driven investigation`。

## 阶段 7：Runbook、策略、审批与隔离执行器

**创建文件：** `src/incident_agent/runbooks/{models,registry,policy,approval,executor}.py`、`apps/executor/main.py`、`tests/integration/runbooks/`、`infra/rbac/*.yaml`。

**交付接口：** restart/scale/rollback 三个版本化 Runbook；`dry_run` 和 `execute`。

1. 写未注册动作、越界 namespace、无审批、审批过期、资源 UID 改变和并发幂等测试。
2. 用 discriminated union 定义三个动作参数，拒绝额外字段和命令文本。
3. 实现策略矩阵：lab 环境低风险 restart 可自动，其余动作需审批。
4. 实现 Approval 状态机、请求哈希、执行记录唯一约束和 dry-run。
5. 用独立 ServiceAccount 启动 Executor，只授予目标 namespace 的必要 verbs。
6. 通过 Kubernetes Python Client 执行动作，并记录 before/after resource version。
7. 提交 `feat: execute approved runbooks with least privilege`。

## 阶段 8：恢复验证、回退和复盘

**创建文件：** `src/incident_agent/verification/{models,policies,service}.py`、`src/incident_agent/reports/postmortem.py`、`tests/e2e/test_incident_lifecycle.py`。

**交付接口：** `VerificationService.verify(policy, incident)->VerificationResult`；只有 successful 结果允许 resolved。

1. 写瞬时恢复、持续恢复、无数据、不恢复和验证超时测试。
2. 为三个故障实现固定稳定窗口和多信号判定策略。
3. 将 not_recovered 作为反证返回 RCA，限制再次处置预算。
4. 生成事实引用的事件摘要和复盘草稿，区分事实、推断和行动项。
5. 跑通三条端到端事件生命周期及审批期间进程重启。
6. 提交 `feat: verify recovery and produce incident reports`。

## 阶段 9：评测、观测与演示

**创建文件：** `evals/{run.py,graders.py,ground_truth/*.json}`、`src/incident_agent/observability/`、`infra/grafana/dashboards/agent.json`、`docs/demo-runbook.md`。

**交付接口：** 单 LLM 基线与 evidence graph runner；版本化 JSON/Markdown 报告。

1. 为 Top-K、证据引用、安全拦截、MTTD/MTTR 和成本计算写测试。
2. 在相同场景、流量、时间窗和模型下执行两种方案，多次运行报告均值与离散度。
3. 增加 node/tool latency、query failures、investigation rounds、tokens 和 approval wait 指标。
4. 运行全部安全、故障注入、恢复与评测流程，并保存失败样例。
5. 用真实报告更新简历文档，录制 8 分钟内演示。
6. 提交 `feat: add reproducible incident evaluation and telemetry`。

## 完成定义

静态检查和默认测试全部通过；实验环境从空集群可重建；三个故障各连续复现三次；未授权动作零执行；审批重启恢复不重复动作；根因和修复结论均可追溯到证据与验证；报告记录环境、版本、费用和失败案例。
