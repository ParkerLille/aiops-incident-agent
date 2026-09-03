# 最小 Incident 闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付无需外部凭证即可运行的 FastAPI 告警摄入、指纹去重、Incident 查询和健康检查闭环。

**Architecture:** 使用 `create_app` 组装可注入 Settings、健康探针和 IncidentRepository。API 层只负责 HTTP，incidents service 负责校验后的业务编排，SQLAlchemy 仓储负责事务与唯一约束；测试默认使用 SQLite 内存库和 Fake 探针，生产配置预留 PostgreSQL/Redis。

**Tech Stack:** Python 3.12、FastAPI、Pydantic Settings v2、SQLAlchemy 2、SQLite/PostgreSQL、pytest、httpx、Ruff、MyPy。

## Global Constraints

- 只允许读取 Alertmanager 告警中的白名单标签和字段；不得持久化完整原始 payload。
- 告警指纹使用规范化 `environment + service + alertname + 核心标签` 的 SHA-256；时间、annotations 和标签顺序不得影响指纹。
- 测试、开发环境不要求 PostgreSQL、Redis、LLM、Kubernetes 或任何外部密钥。
- 生产环境缺失 PostgreSQL URL、Redis URL 或 webhook secret 时启动失败，且不注册 `/v1/lab` 路由。
- 预期错误返回 `application/problem+json`，不泄露连接串、密钥或完整 annotations。
- 每个行为先写失败测试并观察失败，再写最小实现；每项任务通过测试、Ruff、MyPy 后单独使用中文 Conventional Commit 提交。

### Task 1: Python 工程与 Settings

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/incident_agent/__init__.py`
- Create: `src/incident_agent/shared/__init__.py`
- Create: `src/incident_agent/shared/config.py`
- Test: `tests/unit/shared/test_config.py`

**Interfaces:**
- Produces `Settings` with fields `environment`, `database_url`, `redis_url`, `alertmanager_webhook_secret`, `require_webhook_signature`, `max_alert_payload_bytes`.
- Produces `get_settings() -> Settings` cached by `functools.lru_cache`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from pydantic import ValidationError

from incident_agent.shared.config import Settings


def test_development_settings_use_local_defaults():
    settings = Settings(environment="development")
    assert settings.database_url == "sqlite:///./incident-agent.db"
    assert settings.redis_url is None
    assert settings.require_webhook_signature is False


def test_production_settings_require_database_redis_and_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_payload_limit_is_positive():
    with pytest.raises(ValidationError):
        Settings(environment="test", max_alert_payload_bytes=0)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/shared/test_config.py -q`
Expected: FAIL because `incident_agent.shared.config` does not exist.

- [ ] **Step 3: Implement minimal configuration**

```python
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AIOPS_", extra="ignore")

    environment: Literal["test", "development", "production"] = "development"
    database_url: str = "sqlite:///./incident-agent.db"
    redis_url: str | None = None
    alertmanager_webhook_secret: str | None = None
    require_webhook_signature: bool = False
    max_alert_payload_bytes: int = Field(default=1_048_576, gt=0, le=10_485_760)

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if not self.redis_url or not self.alertmanager_webhook_secret:
                raise ValueError("production requires redis_url and alertmanager_webhook_secret")
            self.require_webhook_signature = True
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run tests and static checks**

Run: `pytest tests/unit/shared/test_config.py -q`; `ruff check .`; `mypy src`
Expected: 3 tests pass, Ruff and MyPy exit 0.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore .env.example src tests/unit/shared/test_config.py
git commit -m "chore: 初始化 Python 工程与配置"
```

### Task 2: Database、错误模型与健康探针

**Files:**
- Create: `src/incident_agent/shared/database.py`
- Create: `src/incident_agent/shared/errors.py`
- Create: `src/incident_agent/shared/health.py`
- Test: `tests/unit/shared/test_health.py`

**Interfaces:**
- `create_engine_and_session(database_url) -> tuple[Engine, sessionmaker]`.
- `DependencyProbe` protocol: `async check() -> ProbeResult`.
- `check_dependencies(probes) -> dict[str, ProbeResult]`.
- `ProblemDetails` Pydantic model and `problem_response(...)` helper.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from incident_agent.shared.health import ProbeResult, check_dependencies


@pytest.mark.asyncio
async def test_all_dependencies_ready():
    result = await check_dependencies({"database": lambda: ProbeResult.ok(), "redis": lambda: ProbeResult.disabled()})
    assert result["database"].status == "ok"
    assert result["redis"].status == "disabled"


@pytest.mark.asyncio
async def test_failed_dependency_is_reported_without_raising():
    result = await check_dependencies({"database": lambda: ProbeResult.failed("connection refused")})
    assert result["database"].status == "unavailable"
    assert result["database"].detail == "connection refused"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/shared/test_health.py -q`
Expected: FAIL because health module and ProbeResult do not exist.

- [ ] **Step 3: Implement probe and database primitives**

Implement `ProbeResult` as an immutable dataclass with `status` limited to `ok`, `disabled`, `unavailable`, optional non-secret `detail`, and class constructors `ok()`, `disabled()`, `failed(detail)`. `check_dependencies` must accept sync or async callables, catch exceptions, and convert exception text to `unavailable`.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/unit/shared/test_health.py -q`; `ruff check .`; `mypy src`
Expected: tests pass and static checks exit 0.

```bash
git add src/incident_agent/shared tests/unit/shared/test_health.py
git commit -m "feat: 增加依赖探针与统一错误模型"
```

### Task 3: Alert schemas、指纹与 SQLAlchemy 模型

**Files:**
- Create: `src/incident_agent/incidents/__init__.py`
- Create: `src/incident_agent/incidents/schemas.py`
- Create: `src/incident_agent/incidents/fingerprint.py`
- Create: `src/incident_agent/incidents/models.py`
- Test: `tests/unit/incidents/test_fingerprint.py`
- Test: `tests/unit/incidents/test_schemas.py`

**Interfaces:**
- `AlertmanagerWebhook` and `AlertmanagerAlert` Pydantic models.
- `normalize_labels(labels: Mapping[str, str]) -> dict[str, str]`.
- `compute_fingerprint(labels: Mapping[str, str]) -> str`.
- SQLAlchemy models `Incident`, `Alert`, `TimelineEvent` with a shared declarative `Base`.

- [ ] **Step 1: Write the failing tests**

```python
from incident_agent.incidents.fingerprint import compute_fingerprint


def test_fingerprint_ignores_label_order_and_dynamic_fields():
    first = compute_fingerprint({"service": "orders", "environment": "lab", "alertname": "HighP95", "startsAt": "one"})
    second = compute_fingerprint({"alertname": "HighP95", "environment": "lab", "service": "orders", "startsAt": "two"})
    assert first == second


def test_fingerprint_changes_for_core_label():
    assert compute_fingerprint({"service": "orders", "environment": "lab", "alertname": "HighP95"}) != compute_fingerprint({"service": "payments", "environment": "lab", "alertname": "HighP95"})
```

```python
import pytest
from pydantic import ValidationError
from incident_agent.incidents.schemas import AlertmanagerAlert


def test_alert_requires_core_labels_and_starts_at():
    with pytest.raises(ValidationError):
        AlertmanagerAlert(labels={"service": "orders"}, startsAt="2026-09-04T00:00:00Z")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/incidents -q`
Expected: FAIL because the schema and fingerprint modules do not exist.

- [ ] **Step 3: Implement models and validation**

Require `alertname`, `service`, `environment`, and RFC 3339 `startsAt`; cap labels at 32 entries and key/value lengths at 128/256. Fingerprints serialize sorted core labels excluding `startsAt`, `endsAt`, and annotations with compact JSON, then SHA-256. Add unique Alert fingerprint and Incident foreign key relationships.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/unit/incidents -q`; `ruff check .`; `mypy src`
Expected: all tests pass and checks exit 0.

```bash
git add src/incident_agent/incidents tests/unit/incidents
git commit -m "feat: 建立告警模型与稳定指纹"
```

### Task 4: Incident repository、摄入服务与 API

**Files:**
- Create: `src/incident_agent/incidents/repository.py`
- Create: `src/incident_agent/incidents/service.py`
- Create: `src/incident_agent/incidents/router.py`
- Create: `apps/api/__init__.py`
- Create: `apps/api/main.py`
- Test: `tests/integration/incidents/test_alert_ingestion.py`
- Test: `tests/smoke/test_health.py`

**Interfaces:**
- `IncidentRepository.ingest_alert(alert) -> IngestedAlert`.
- `IncidentRepository.get_incident(incident_id) -> IncidentView | None`.
- `AlertIngestService.ingest(payload, raw_body, headers) -> IngestResponse`.
- `create_app(settings=None, repository=None, probes=None) -> FastAPI`.

- [ ] **Step 1: Write failing integration and smoke tests**

```python
def test_duplicate_webhook_reuses_incident(client, webhook_payload):
    first = client.post("/v1/alerts/alertmanager", json=webhook_payload)
    second = client.post("/v1/alerts/alertmanager", json=webhook_payload)
    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["incident_ids"] == first.json()["incident_ids"]
    assert second.json()["duplicate_alerts"] == 1


def test_same_batch_groups_by_environment_and_service(client, webhook_payload):
    payload = {"alerts": [webhook_payload["alerts"][0], {**webhook_payload["alerts"][0], "labels": {**webhook_payload["alerts"][0]["labels"], "service": "inventory"}}]}
    response = client.post("/v1/alerts/alertmanager", json=payload)
    assert response.status_code == 202
    assert len(response.json()["incident_ids"]) == 2


def test_incident_query_returns_timeline(client, webhook_payload):
    created = client.post("/v1/alerts/alertmanager", json=webhook_payload).json()
    response = client.get(f"/v1/incidents/{created['incident_ids'][0]}")
    assert response.status_code == 200
    assert [event["type"] for event in response.json()["timeline"]] == ["incident_created", "alert_received"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/integration/incidents tests/smoke/test_health.py -q`
Expected: FAIL because the application factory and repository do not exist.

- [ ] **Step 3: Implement transaction-safe ingestion**

Within one transaction, normalize each alert, find or create the `environment + service` Incident, insert Alert by unique fingerprint, and on `IntegrityError` roll back only the insert savepoint then query the existing Alert. Create timeline events only for new Incident and new Alert. Return created IDs and duplicate count. Register `/live`, `/ready`, POST ingestion, and GET incident routes. Enforce body size before JSON parsing and return Problem Details for validation, auth, missing incident, and dependency errors.

- [ ] **Step 4: Run focused tests and repair failures**

Run: `pytest tests/integration/incidents tests/smoke/test_health.py -q`
Expected: all ingestion and health tests pass. For each failure, capture the traceback, reproduce with the smallest test, apply one root-cause fix, and rerun the focused test before the full suite.

- [ ] **Step 5: Run full checks and commit**

Run: `pytest -q`; `ruff check .`; `ruff format --check .`; `mypy src apps`
Expected: all tests pass with no lint, format, or type errors.

```bash
git add apps src tests
git commit -m "feat: 跑通告警归并与事件查询闭环"
```

### Task 5: Compose、文档与本地冒烟验证

**Files:**
- Create: `compose.yaml`
- Create: `apps/api/__main__.py`
- Modify: `README.md`
- Create: `tests/smoke/test_local_startup.py`

- [ ] **Step 1: Add startup smoke test**

Start the app with `AIOPS_ENVIRONMENT=development` and SQLite defaults, request `/live` and `/ready`, and assert both return 200 without PostgreSQL, Redis, or secret configuration.

- [ ] **Step 2: Implement local startup and Compose**

Expose `python -m apps.api` using Uvicorn on `0.0.0.0:8000`. Compose must run the API with a healthcheck and no mandatory external service for the default profile; database/redis profiles are optional and documented.

- [ ] **Step 3: Verify and commit**

Run: `pytest -q`; `docker compose config`; `python -m apps.api` in a separate terminal and invoke `Invoke-WebRequest http://127.0.0.1:8000/live`.
Expected: tests pass, Compose config validates, and live endpoint returns HTTP 200.

```bash
git add compose.yaml apps/api/__main__.py README.md tests/smoke/test_local_startup.py
git commit -m "chore: 完善本地启动与开发说明"
```
