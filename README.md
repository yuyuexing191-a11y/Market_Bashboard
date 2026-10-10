# Market_Bashboard

股票行情查看器的开发课程项目，目标是展示股票列表、历史 K 线、指标和行情排名。当前课程规划 Issue 02 提供固定股票池、本地 Parquet 数据源检查脚本，以及 PostgreSQL 16 开发环境；尚未提供可运行的 Web 看板。本地历史数据不等于实时行情。

当前 Compose 只准备数据库环境。行情表、迁移和 Parquet 导入属于课程规划 Issue 03。

## 准备环境

从仓库根目录执行以下命令。需要可用的 Docker Engine、支持 `up --wait` 的 Docker Compose、`uv`，以及能够读取的本地数据目录 `/mnt/glusterfs/quantdata/tushare/`。首次运行需要能够获取 PostgreSQL 镜像和 Python 依赖；数据检查只读本地文件，不调用在线 Tushare API。

```bash
docker compose version
uv --version
ls /mnt/glusterfs/quantdata/tushare/
```

创建本机配置，保留已经存在的 `.env`：

```bash
if [ ! -e .env ]; then
  cp .env.example .env
fi
```

`.env` 不提交到仓库；可按需编辑其中的 `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 和 `DB_PORT`。默认数据库与用户均为 `market_dashboard`，默认宿主机端口为 `5432`。示例凭据只用于本机开发。已初始化的数据卷不会因修改 `.env` 自动更新数据库用户或密码。

## 启动数据库

首次启动前检查默认端口是否占用（Linux）：

```bash
ss -ltn '( sport = :5432 )'
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

本项目验证机器上的 `stock-market-postgres` 使用了 `5432`。其他机器可能没有这个容器；只有确认占用端口的正是该容器、并允许临时停止它时，才在同一 Bash 会话执行以下步骤。若占用者是其他服务，应先处理该服务的冲突，或在 `.env` 调整 `DB_PORT` 后检查新端口。

```bash
original_postgres_stopped=false
if [ "$(docker inspect -f '{{.State.Running}}' stock-market-postgres 2>/dev/null)" = true ]; then
  docker stop stock-market-postgres && original_postgres_stopped=true
fi
```

等待数据库健康后再连接：

```bash
docker compose config --quiet
docker compose up -d --wait --wait-timeout 90
docker compose ps
docker compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database(), current_user;"'
```

以上命令使用容器中的实际配置。若保留默认 `.env`，健康检查也可以写为：

```bash
docker compose exec -T postgres pg_isready -U market_dashboard -d market_dashboard
```

安装了宿主机 `psql` 时，也可从宿主机连接，按提示输入 `.env` 中的密码；修改过配置时替换端口、用户名和数据库名：

```bash
psql -h 127.0.0.1 -p 5432 -U market_dashboard -d market_dashboard -W \
  -c 'SELECT current_database(), current_user;'
```

## 检查数据源

检查固定的 [20 只股票配置](config/stock_pool.csv)，自动选择日线与分钟线均覆盖所有配置代码的最新共同日期：

```bash
uv run --with duckdb python scripts/check_source_data.py \
  --data-root /mnt/glusterfs/quantdata/tushare \
  --stock-pool config/stock_pool.csv
```

指定日期并输出 JSON；指定日期没有满足覆盖条件时会报错，不回退到其他日期：

```bash
uv run --with duckdb python scripts/check_source_data.py \
  --data-root /mnt/glusterfs/quantdata/tushare \
  --stock-pool config/stock_pool.csv \
  --date 2026-10-09 --format json
```

报告包含上市状态、日线和分钟代码覆盖、各股票分钟记录数，以及日线成交量和成交额。共同覆盖仅表示每只股票有记录，不证明分钟序列连续或源文件已经写完，也不是股票流动性的量化证明。字段、分区和口径见 [数据源学习笔记](plan/learning/03.md)。

脚本测试使用临时构造的 Parquet 数据，不要求数据库启动，也不修改真实源目录：

```bash
uv run --with duckdb --with pytest python -m pytest tests/test_check_source_data.py -q
```

## 停止与恢复

使用命名卷 `market_dashboard_postgres_data` 保存数据库。停止本项目会移除容器和网络，保留数据卷：

```bash
docker compose down
```

若前面临时停止了 `stock-market-postgres`，必须先完成本项目的 `down`、释放端口，再在同一 Bash 会话恢复原容器：

```bash
if [ "${original_postgres_stopped:-false}" = true ]; then
  docker start stock-market-postgres
  docker inspect -f 'running={{.State.Running}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' stock-market-postgres
fi
```

启动或检查失败时也按此顺序清理和恢复。原容器本来未运行、或根本不存在时，不执行恢复。`docker compose down -v` 会删除数据库数据，课程规划 Issue 02 验收禁止使用。

## 验证记录与项目文档

2026-10-10 的 [源数据检查证据](evidence/source-check.txt) 记录了日期 `2026-10-09`：20 只股票均为 `list_status=L`，日线与分钟代码均覆盖 20 只，每只股票有 241 条分钟记录。[数据库验证证据](evidence/postgres-check.txt) 记录 PostgreSQL 16.15 的健康状态、容器内 SQL、宿主机 TCP 密码连接、重启和 `down` 后重建的持久化验证；临时测试表已删除。本项目验证后已 `down` 并保留命名卷，原容器已恢复运行且健康。这些是当时的验证记录，启动自己的环境时仍需执行上面的检查。

- [课程设计](plan/course-plan.md) 与 [课程任务规划](plan/course-issues.md)
- [Git 流程学习](plan/learning/01.md) 与 [课程规划 Issue 02 学习笔记（原步骤 03）](plan/learning/03.md)
- [GitHub 任务跟踪约定](docs/agents/issue-tracker.md)、[任务分诊标签](docs/agents/triage-labels.md)、[领域文档约定](docs/agents/domain.md)

课程规划编号不是 GitHub Issue 编号。本任务的真实 GitHub Issue 因 `gh` 尚未登录仍待创建或确认；关联 PR 时必须使用真实编号。开发分支为 `feat/data_environment`，不得直接向 `main` 提交或推送。PR 的创建和合入由人工完成。
