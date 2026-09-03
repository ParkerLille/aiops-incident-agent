# AIOps Incident Agent

面向微服务系统的故障诊断与受控处置平台。系统接收告警，聚合指标、日志、调用链和发布变更，由多个受限调查 Agent 并行收集证据、形成根因排序，并通过预定义 Runbook 与人工审批执行恢复动作。

> 当前状态：离线最小闭环已实现并通过 48 项自动化测试；真实 Prometheus/Loki/Tempo/Kubernetes 适配仍保留为后续实验环境扩展。本项目运行在自建故障实验环境，不代表真实生产事故数据。

## 快速开始

Python 3.12 环境下直接安装并启动：

```powershell
python -m pip install -e ".[dev]"
python -m apps.api
```

默认开发模式使用 SQLite 和 Fake Redis 探针，不需要外部密钥。启动后可访问：

- `GET http://127.0.0.1:8000/live`
- `GET http://127.0.0.1:8000/ready`
- `GET http://127.0.0.1:8000/v1/lab/scenarios`
- `POST http://127.0.0.1:8000/v1/alerts/alertmanager`
- `GET http://127.0.0.1:8000/v1/incidents/{incident_id}`

运行验证：

```powershell
pytest -q
ruff check src apps tests
ruff format --check src apps tests
python -m mypy src
docker compose config
```

生产模式要求 PostgreSQL、Redis 和 webhook secret；`/v1/lab` 路由不会注册。未配置 LLM、遥测或 Kubernetes 时，调查器使用确定性 Fake 或明确返回 missing-source，不会伪造事实。

## 首版故障范围

1. Order Service 数据库慢查询导致接口 P95 上升。
2. Inventory Service Redis 连接池耗尽导致级联超时。
3. Payment Service 错误配置导致调用链大量 5xx。

首版处置动作限定为重启 Deployment、扩容副本和回滚上一版本。Agent 不生成或执行任意 Shell 命令。

## 核心工程目标

- 由协调器规划调查，指标、日志、Trace 和变更 Agent 并行收集结构化证据。
- 每项根因结论同时记录支持证据、反证、置信度和来源查询。
- Runbook 使用参数 Schema、RBAC、风险等级、审批、幂等键、超时和恢复验证。
- 遥测缺失或证据不足时明确转人工，不允许模型用常识补齐事实。
- 通过可重复故障注入评估 Top-1/Top-3 根因命中率、MTTD、MTTR、安全拦截和成本。

## 规划技术栈

- Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2、Alembic
- LangGraph、PostgreSQL Checkpointer、Redis、Celery
- OpenTelemetry、Prometheus、Loki、Tempo、Grafana
- Kubernetes Python Client、kind 或 k3d
- Pytest、Testcontainers、Ruff、MyPy
- Docker Compose + Helm/Kustomize（仅实验环境）

## 目标目录结构

```text
aiops-incident-agent/
├── apps/
│   ├── api/                     # 告警入口、事件 API、审批和 SSE
│   └── worker/                  # 长时间调查与报告任务
├── src/incident_agent/
│   ├── incidents/               # 告警聚合、事件状态与时间线
│   ├── topology/                # 服务拓扑与依赖关系
│   ├── investigators/           # Metrics/Logs/Trace/Change 调查器
│   ├── reasoning/               # 假设、证据评分与根因排序
│   ├── runbooks/                # 注册表、策略、审批和执行器
│   ├── verification/            # 恢复判定和回退逻辑
│   ├── reports/                 # 事件摘要与复盘报告
│   ├── observability/           # Agent 自身 trace、指标和审计
│   └── shared/                  # 配置、数据库、错误模型
├── lab/                         # 可观测微服务和故障注入场景
├── tests/                       # 单元、集成、契约和端到端测试
├── evals/                       # 真值、runner、grader 和报告
├── infra/                       # Compose、kind、Grafana 配置
├── docs/                        # 设计、计划、简历与面试材料
└── pyproject.toml
```

## 文档导航

- [项目规格](docs/01-project-spec.md)
- [系统架构](docs/02-architecture.md)
- [模块拆分](docs/03-module-breakdown.md)
- [开发顺序](docs/04-development-roadmap.md)
- [评测与验收](docs/05-evaluation.md)
- [简历表述](docs/06-resume-material.md)
- [面试追问题库](docs/07-interview-question-bank.md)
