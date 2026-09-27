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
5. **DrawWeighing（出胶称重）**：`hearth`（所属灶台）、`weighedAt`、`netKg`（净重，须为正）、`weigherName`（司秤人）

**业务规则**：

- 将灶台相位切到 `drawing`（出胶）时，进行中的 CookRun 必须至少有一条 SoftPointProbe 的 `softPointC ≤ 95`。
- **出胶称重联锁**（`apps/kiln/services/floor_rules.py`）：
  - 仅 `drawing`（出胶）相位灶台可登记称重，其它相位拒绝；净重须为正数。
  - 累计口径：同灶、当前未收灶值守期间（称重时刻 ≥ 开灶时刻）的净重合计，称重登记与收灶判定共用同一口径（`draw_weigh_summary`）。
  - 累计净重不得超过当前值守来脂批的 `arrivalKg`（到货量），超出拒绝并回显已累计量。
  - **半额口径**：收灶回冷灶时，须至少存在一条称重，且累计净重 ≥ 到货量 × 50%（按 0.01kg 向上取整），否则拒绝收灶。
  - 收灶统一走 `close_run_to_cold`，先过称重联锁再落库，禁止收灶成功却不查称重。

## 界面

- 首页：**灶台值守看板** — 左侧班次条 + 按过道排布的灶台瓦片；点瓦片打开右侧抽屉（值守、探针时间线、出胶称重累计与登记、改相位 / 登记探针 / 开灶）
- 次页：**来脂批** — 卡片时间线，非宽表 CRUD
- 班次条新增：**出胶称重**（秤）— 各灶称重流水；抽屉内展示当前值守累计净重 / 到货量 / 半额收灶线

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有灶台则只保证账号存在。样例地名仅用「松脂坳 / 桐油坑」系。出胶灶「坑火-西一」刻意不种任何称重记录，用于演示收灶联锁。

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
