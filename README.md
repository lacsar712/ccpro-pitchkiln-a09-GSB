# PitchKiln-01 · 灶台值守看板

Django 5 + PostgreSQL：灶台瓦片看板 + 右侧抽屉探针时间线，无 Vue/React SPA。

## 技术栈

- Django 5、PostgreSQL
- Session 登录
- HTMX：局部刷新灶台网格与抽屉
- Docker Compose：`web` + `db`

## 端口与数据库

| 服务 | 端口 |
|------|------|
| Web  | **4710** |
| Postgres | **6110**（容器内 5432） |

数据库账号：`pitchkiln` / `pitchkiln` / 库名 `pitchkiln`

## 快速启动

```bash
cd PitchKiln/PitchKiln-01
docker compose up --build -d
```

浏览器打开：http://localhost:4710

演示账号：

- `admin` / `123456`（超级用户）
- `worker` / `123456`（普通用户）

容器启动时会自动：`migrate` → `seed_data` → `collectstatic` → `gunicorn`

## 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 确保本机 Postgres 监听 6110，或先 docker compose up -d db
set POSTGRES_HOST=localhost
set POSTGRES_PORT=6110
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:4710
```

## 业务模型

1. **ResinLot（来脂批）**：`lotCode`、`originPlace`、`arrivalKg`、`receivedAt`
2. **FireHearth（灶台）**：`lane`、`tag`（唯一）、`resinGrade`、相位 `cold|charging|ramping|holding|drawing`
3. **CookRun（熬制值守）**：归属灶台与来脂批、`openedAt`、`closedAt`（可空）、`targetSoftPointC`
4. **SoftPointProbe（软化点探针）**：归属值守、`sampledAt`、`softPointC`、`samplerName`
5. **DrawingWeigh（出胶称重）**：归属值守（所属灶台即值守所在灶）、`weighedAt`、`netKg`（须为正）、`weigherName`

**业务规则**：将灶台相位切到 `drawing`（出胶）时，进行中的 CookRun 必须至少有一条 SoftPointProbe 的 `softPointC ≤ 95`。逻辑在 `apps/kiln/services/floor_rules.py`，由相位切换入口调用。

**出胶称重联锁**（同在 `floor_rules.py`）：

- 仅 `drawing`（出胶）相位灶台可登记称重，其它相位拒绝；净重须为正。
- 同一值守未收灶期间，累计净重不得超过该值守来脂批的到货千克；超出拒绝并在错误信息中回显已累计量。
- 出胶灶收灶回冷灶的**半额口径**：须至少存在一条称重，且累计净重 ≥ 当前值守来脂批到货千克 ÷ 2，否则拒绝收灶。非出胶相位收灶不触发该联锁。
- 称重登记与收灶判定共用 `weigh_total_kg` 同一累计口径；收灶只能走 `close_run_to_cold` 统一入口，不存在不查称重的收灶路径。
- 出胶相位不能经「改相位」直接改回冷灶，须走收灶入口过联锁。

## 界面

- 首页：**灶台值守看板** — 左侧班次条 + 按过道排布的灶台瓦片；点瓦片打开右侧抽屉（值守、出胶称重累计、探针时间线、改相位 / 登记探针 / 开灶）
- 班次条「称」：**出胶称重台** — 列出全部出胶相位灶台，逐灶登记称重并展示累计净重 / 剩余可称 / 半额门槛
- 次页：**来脂批** — 卡片时间线，非宽表 CRUD

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有灶台则只保证账号存在。样例地名仅用「松脂坳 / 桐油坑」系。出胶灶「坑火-西一」刻意不留任何称重，用于演示收灶联锁（无合格称重不得收灶回冷灶）。

## 目录结构

```
PitchKiln-01/
  manage.py
  requirements.txt
  Dockerfile
  entrypoint.sh
  docker-compose.yml
  config/
  apps/kiln/          # 模型、视图、floor_rules、种子
  templates/floor/    # 值守看板 + 抽屉
  templates/resin/    # 来脂批时间线
  static/css/         # 值守台 ops-console 样式
```
