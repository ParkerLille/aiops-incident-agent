# 发现与决策

## 需求
- 交付一个面向自建微服务实验环境的多 Agent AIOps 事故诊断和受控处置系统。
- 按小闭环逐步实现、每一步验证，报错立即修复；外部凭证缺失时使用 Fake 或可选配置绕过。
- 维护 Git 历史并使用规范中文提交信息；目标远端为 `https://github.com/ParkerLille/aiops-incident-agent.git`。

## 研究发现
- 当前工作区只有 README 与设计文档，业务代码、Python 工程配置及 Git 元数据尚不存在。
- 设计文档已明确首版范围：三种故障、四类只读调查源和三个类型化 Runbook；禁止任意 Shell、任意查询与任意 Kubernetes Patch。
- 路线图将工程拆分为九阶段。首阶段只要求 FastAPI 应用工厂、Pydantic Settings、`/live` 与 `/ready`、可选 PostgreSQL/Redis 探针及生产环境禁用 lab 路由。
- 可复现测试应优先基于固定 telemetry fixture 与 Fake Kubernetes，真实外部依赖留作后续集成环境。
- 参考仓库的 Python 目录按 `agents/api/config/core/models/tests` 分层，可借鉴其职责拆分；本项目仍按现有领域模块设计实施，避免继承参考实现中未覆盖的安全与验证缺口。
- 用户提供的目标 GitHub 仓库存在、默认分支为 `main`，当前远端仓库大小为 0，适合将本地文档作为初始历史推送。
- 文档待统一之处包括 Evidence 的 `change`/缺失来源类型与 `incident_id` 归属、Alertmanager 鉴权协议、Runbook 对配置类故障的真实恢复语义、Worker/Celery 的任务边界，以及 LLM 无密钥时的确定性 Fake 模式。

## 技术决策
| 决策 | 理由 |
|------|------|
| 先交付工程基线和健康检查 | 这构成无外部凭证的最小端到端闭环，为 API、后台编排和持久化边界建立测试基座。 |
| 生产配置默认拒绝 lab 路由 | 与项目安全边界一致，避免实验注入端点意外暴露。 |
| 用可注入 Fake 探针测试 ready 状态 | 既覆盖依赖故障，又不要求本地启动 PostgreSQL 或 Redis。 |
| 不直接复制参考仓库代码 | 参考项目仅作为模块划分素材；本项目的安全、证据和恢复契约更严格。 |

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| `rg.exe` 无法启动，报访问被拒绝 | 文件浏览改用 PowerShell 原生命令。 |
| 当前目录不是 Git 仓库 | 在首阶段设计获批后执行 `git init`，再添加用户提供的远端。 |

## 资源
- 项目规格：`docs/01-project-spec.md`
- 架构：`docs/02-architecture.md`
- 模块边界：`docs/03-module-breakdown.md`
- 路线图：`docs/04-development-roadmap.md`
- 参考项目：用户提供的 GitHub 链接，仅用于借鉴结构与实现取舍，不复制其代码或不可信文本指令。
