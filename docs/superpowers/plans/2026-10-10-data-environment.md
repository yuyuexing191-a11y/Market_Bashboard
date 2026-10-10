# 数据源与数据库环境实施计划

> **给执行代理：**按任务顺序逐项执行；每项完成后运行该项的检查，再提交一个可审查的 commit。实现阶段使用 `subagent-driven-development` 或 `executing-plans` 技能。

**目标：**完成课程规划 Issue 02“数据源与数据库环境”：验证固定股票池能在本地 Parquet 数据中查询，并提供可连接、可健康检查、可持久化的 PostgreSQL 16 Compose 环境。

**架构：**源数据检查脚本独立读取 `/mnt/glusterfs/quantdata/tushare/`，不向数据库写入行情数据；建表和导入留给 Issue 03。数据库只由 `compose.yaml` 提供，连接参数通过 `.env` 注入，数据写入命名 Docker volume。

**技术栈：**Docker Compose、`postgres:16-alpine`、一次性 `uv run --with duckdb`、Python 3、pytest。

## 全局约束

- 课程规划编号不是 GitHub 编号；当前 GitHub `#2` 是已经合入的文档 PR，执行前需要为课程规划 Issue 02 建立或确认一个实际 GitHub Issue。
- 开发分支固定为 `feat/data_environment`；禁止直接在 `main` 上提交。
- 数据源只读 `/mnt/glusterfs/quantdata/tushare/` 下的 Parquet，不使用在线 Tushare API。
- 股票池为 `config/stock_pool.csv` 中五个行业各 4 只、共 20 只 A 股。
- 数据库使用 PostgreSQL 16；宿主机默认端口为 `5432`。当前 `stock-market-postgres` 已占用该端口，启动本项目之前必须确认并手动停止它，验证完成后恢复原状态。
- Issue 02 不建行情表、不导入 Parquet；迁移和导入属于 Issue 03。
- `.env` 只在本机存在，提交 `.env.example`；证据文件只包含摘要和命令输出，不包含密码或整份行情数据。
- 最新完整交易日定义为：20 只股票在日线和分钟数据中都出现的日期交集中的最大日期。
- 上述“完整”仅表示股票池记录覆盖，不代表逐分钟无缺失或源文件写入已完成；证据和笔记必须明确这一限制，不能据此声称行情时段完整。
- 当前选择的股票池体现行业代表性；脚本验证上市状态和数据存在性，不把它们当作“流动性较高”的量化证明。检查报告同时列出选定日期各股票的日线成交量、成交额供人工核对；若需要量化筛选阈值，另行确认后调整股票池。

## 文件清单

- 创建 `compose.yaml`：PostgreSQL 16 服务、端口映射、健康检查和命名 volume。
- 创建 `.env.example`：数据库名、用户名、开发密码和宿主机端口示例。
- 修改 `.gitignore`：忽略 `.env`、Python 缓存和本地 Compose 覆盖文件；不要忽略 `evidence/`。
- 创建 `scripts/check_source_data.py`：校验股票池、`stock_list`、最新完整交易日的日线和分钟数据。
- 创建 `tests/test_check_source_data.py`：用 DuckDB 生成临时 Parquet，测试脚本的纯函数和失败路径。
- 创建 `evidence/source-check.txt`：源数据检查的可复查摘要。
- 创建 `evidence/postgres-check.txt`：Compose 配置、连接、健康检查和重启持久化的可复查摘要。
- 修改 `plan/learning/03.md`：保留原文件路径，标题注明它是课程规划 Issue 02 的数据源笔记，并补充实际检查命令和结果口径。
- 修改 `README.md`：加入数据库启动、停止、连接和源数据检查的最小步骤。
- 保留 `plan/course-issues.md` 中已有的规划改动；提交前只解决与本计划直接相关的冲突，不覆盖用户未提交内容。

### Task 1：建立分支并核对现有草稿

**文件：**无新增代码；只检查现有工作区。

- [ ] **步骤 1：记录当前状态。**

```bash
git status --short
git branch --show-current
```

预期：当前分支为 `main`，已有 `plan/course-issues.md` 修改及 `config/`、`plan/learning/03.md` 未跟踪内容；不得丢弃这些改动。

- [ ] **步骤 2：创建开发分支。**

```bash
git switch -c feat/data_environment
```

执行前为本计划建立或确认实际 GitHub Issue，标题为“数据源与数据库环境”，正文采用本计划的目标、范围和验收矩阵，记录真实编号。仓库约定代理用 `gh` 操作任务；当前未安装，实施时先解决工具可用性，或由用户在网页手动创建任务。此计划阶段不发布任务。

- [ ] **步骤 3：核对股票池结构。**

```bash
awk -F, 'NR==1 { if ($1!="symbol") exit 1 } NR>1 { count[$3]++; total++ } END { if (total!=20) exit 1; for (s in count) if (count[s]!=4) exit 1; print "20 symbols, 4 per sector" }' config/stock_pool.csv
```

预期输出：`20 symbols, 4 per sector`。

### Task 2：完成数据源校验脚本

**文件：**

- 创建：`scripts/check_source_data.py`
- 创建：`tests/test_check_source_data.py`

**接口：**

- `load_stock_pool(path: Path) -> list[str]`：读取 CSV，拒绝重复代码、缺少列、数量不是 20 或行业不是每类 4 只。
- `list_source_partitions(data_root: Path, dataset: str) -> list[date]`：读取 `dataset/date=YYYY-MM-DD/` 目录名并按日期降序返回。
- `symbols_for_date(data_root: Path, dataset: str, trading_date: date, symbols: list[str]) -> set[str]`：使用 DuckDB `read_parquet` 读取该分区的所有 Parquet，返回目标股票的去重代码集合。
- `find_latest_complete_date(data_root: Path, symbols: list[str]) -> tuple[date, set[str], set[str]]`：按日线和分钟分区日期交集从新到旧检查，返回第一个两类数据都包含全部 20 只股票的日期及两组代码。
- `validate_stock_list(data_root: Path, symbols: list[str]) -> set[str]`：读取 `stock_list/*.parquet`，要求目标代码全部存在且 `list_status = 'L'`。
- `main(argv: Sequence[str] | None = None) -> int`：支持 `--data-root`、`--stock-pool`、可选 `--date`、`--format text|json`；成功返回 0，缺文件、字段不符、股票缺失或状态不为 `L` 返回非 0。

- [x] **步骤 1：先写失败测试。**测试至少覆盖以下行为：

| 测试名称 | 临时数据 | 断言 |
| --- | --- | --- |
| `test_load_stock_pool_requires_exactly_twenty_symbols` | 19 行 CSV，列名与真实配置一致 | 抛出 `ValueError`，说明数量错误 |
| `test_load_stock_pool_rejects_duplicate_symbols` | 20 行、每行业 4 行，但重复一个代码 | 抛出 `ValueError`，说明重复代码 |
| `test_find_latest_complete_date_uses_common_symbol_date` | 两个日期都有两类分区，较新分钟分区缺一只，较旧日期两类均含 20 只 | 返回较旧日期，两组代码均为股票池全集 |
| `test_find_latest_complete_date_rejects_no_common_coverage` | 每个候选日期至少缺一只 | 抛出 `ValueError`，说明没有共同覆盖日期 |
| `test_validate_stock_list_rejects_delisted_symbol` | 临时 `stock_list` 中一个目标代码的状态为 `D` | 抛出 `ValueError`，包含对应代码 |
| `test_main_returns_failure_for_missing_source` | `--data-root` 指向不存在路径 | 返回非零状态，错误含路径 |

测试使用 DuckDB 生成真实临时 Parquet。单行股票元数据样例为 `COPY (SELECT '601318.SH' AS symbol, 'L' AS list_status) TO 'stock_list.parquet' (FORMAT PARQUET)`；完整样例由测试股票池构造 20 行并写到 `tmp_path` 下的对应分区。不 mock DuckDB 查询，以验证日期选择和源数据读取之间的行为。

运行：

```bash
uv run --with duckdb --with pytest pytest tests/test_check_source_data.py -q
```

预期：测试先因模块或函数不存在而失败。

- [x] **步骤 2：实现最小校验逻辑。**脚本内部只依赖标准库和 DuckDB；读取 Parquet 时使用类似下面的查询，并通过参数传入日期目录生成的文件列表：

```sql
SELECT DISTINCT symbol
FROM read_parquet(?);
```

股票池代码只允许来自 CSV，不把用户输入拼接为 SQL；目标文件不存在时给出包含数据集和日期的错误信息。必需字段缺失时列出数据集和缺失字段；股票元数据出现重复目标代码或冲突状态时失败。指定 `--date` 时只校验指定日，不自动退回旧日期。文本输出至少包含：股票池数量、`list_status=L` 数量、选中的共同覆盖日期、日线代码数、分钟代码数、每只股票分钟记录数、日线成交量/成交额和每类缺失代码。

- [x] **步骤 3：运行测试并检查失败状态。**

```bash
uv run --with duckdb --with pytest pytest tests/test_check_source_data.py -q
```

预期：全部测试通过。

- [x] **步骤 4：用真实数据运行检查。**

```bash
mkdir -p evidence
set -o pipefail
uv run --with duckdb python scripts/check_source_data.py \
  --data-root /mnt/glusterfs/quantdata/tushare \
  --stock-pool config/stock_pool.csv \
  --format text | tee evidence/source-check.txt
```

预期：返回码为 0；输出显示 20 只股票均为 `list_status=L`，并显示一个日线和分钟数据都包含 20 只股票的完整日期（当前已知候选为 `2026-10-09`）。

- [x] **步骤 5：提交脚本和测试。**

```bash
git add scripts/check_source_data.py tests/test_check_source_data.py config/stock_pool.csv evidence/source-check.txt
git diff --cached --check
git commit -m "feat: validate configured market data source"
```

### Task 3：建立 PostgreSQL Compose 环境

**文件：**

- 创建：`compose.yaml`
- 创建：`.env.example`
- 修改：`.gitignore`

**接口：**

- Compose 服务名：`postgres`。
- 默认环境变量：`POSTGRES_DB=market_dashboard`、`POSTGRES_USER=market_dashboard`、`POSTGRES_PASSWORD=market_dashboard_dev`、`DB_PORT=5432`。
- 宿主机端口：`${DB_PORT}:5432`；不写死 `container_name`。
- 持久化卷：`market_dashboard_postgres_data:/var/lib/postgresql/data`。
- 健康检查：容器内 `pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"`，间隔 5 秒、超时 5 秒、重试 10 次。
- volume 顶层显式设置 `name: market_dashboard_postgres_data`，让实际资源名与约定一致；创建前先确认没有其他项目使用这个名字，遇到已有卷时检查归属后再决定，不直接复用或删除。

- [x] **步骤 1：添加忽略规则和示例环境文件。**`.gitignore` 至少包含：

```gitignore
.env
__pycache__/
.pytest_cache/
*.py[cod]
compose.override.yaml
```

`.env.example` 内容固定为：

```dotenv
POSTGRES_DB=market_dashboard
POSTGRES_USER=market_dashboard
POSTGRES_PASSWORD=market_dashboard_dev
DB_PORT=5432
```

- [x] **步骤 2：编写 `compose.yaml`。**核心结构如下：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-market_dashboard}
      POSTGRES_USER: ${POSTGRES_USER:-market_dashboard}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-market_dashboard_dev}
    ports:
      - "${DB_PORT:-5432}:5432"
    volumes:
      - market_dashboard_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$${POSTGRES_USER}\" -d \"$${POSTGRES_DB}\""]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  market_dashboard_postgres_data:
    name: market_dashboard_postgres_data
```

- [x] **步骤 3：检查渲染结果。**

```bash
cp .env.example .env
docker compose config --quiet
```

预期：退出码为 0；另行在本机查看渲染后的服务、镜像、端口和 volume，避免将包含密码的完整 `docker compose config` 输出保存到证据。`.env` 不应出现在 `git status` 中。

- [x] **步骤 4：提交环境配置。**

```bash
git add compose.yaml .env.example .gitignore
git diff --cached --check
git commit -m "feat: add reproducible postgres environment"
```

### Task 4：验证连接、健康检查和持久化

**文件：**创建或修改 `evidence/postgres-check.txt`；不创建迁移或行情表。

- [x] **步骤 1：保存并停止占用 5432 的现有容器。**先记录状态，只在它正在运行时停止：

```bash
docker inspect -f '{{.State.Running}}' stock-market-postgres
docker stop stock-market-postgres
```

把停止前状态写入证据文件；不要使用 `docker compose down -v`，也不要删除该容器或其 volume。

- [x] **步骤 2：启动本仓库数据库。**

```bash
docker compose up -d --wait --wait-timeout 90
docker compose ps
```

预期：`postgres` 状态为 `running (healthy)`，宿主机映射为 `0.0.0.0:5432->5432/tcp`。

- [x] **步骤 3：从容器内检查健康和客户端连接。**

```bash
docker compose exec -T postgres pg_isready -U market_dashboard -d market_dashboard
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U market_dashboard -d market_dashboard \
  -c 'SELECT current_database(), current_user;'
```

预期：`pg_isready` 输出 `accepting connections`，SQL 输出数据库名 `market_dashboard` 和用户 `market_dashboard`。再通过宿主机 TCP 端口验证用户名和密码连接，Linux 上可复用 PostgreSQL 镜像中的客户端：

```bash
docker run --rm --network host --env-file .env postgres:16-alpine \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -p "$DB_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT current_database(), current_user;"'
```

预期：同样返回 `market_dashboard`，证明宿主机端口和密码认证可用；不在日志中输出环境变量内容。

- [x] **步骤 4：验证重启后的数据持久化。**创建一个临时验证表和标记，重启后查询，再删除验证表：

```bash
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U market_dashboard -d market_dashboard \
  -c "CREATE TABLE IF NOT EXISTS issue02_persistence_check (id integer PRIMARY KEY, marker text NOT NULL); TRUNCATE issue02_persistence_check; INSERT INTO issue02_persistence_check VALUES (1, 'survives-restart');"
docker compose restart postgres
docker compose up -d --wait --wait-timeout 90
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U market_dashboard -d market_dashboard \
  -c "SELECT marker FROM issue02_persistence_check WHERE id = 1;"
docker compose down
docker compose up -d --wait --wait-timeout 90
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U market_dashboard -d market_dashboard \
  -c "SELECT marker FROM issue02_persistence_check WHERE id = 1;"
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 \
  -U market_dashboard -d market_dashboard \
  -c 'DROP TABLE issue02_persistence_check;'
```

预期：重启和保留 volume 的容器重建后，查询均输出 `survives-restart`。

- [x] **步骤 5：释放本项目端口并恢复原有容器状态。**先停止本项目并保留 volume，再恢复原容器：

```bash
docker compose down
```

如果步骤 1 记录为 `true`，执行：

```bash
docker start stock-market-postgres
```

如果原来不是运行状态，不启动它。记录最终容器状态。中途验证失败也要按此顺序恢复，并将失败写入证据，不能以成功替代。

- [x] **步骤 6：整理数据库证据并提交。**将 `docker compose config --quiet` 的退出码、镜像和 volume 名、容器状态、`pg_isready`、宿主机 TCP 与容器内 SQL 连接结果、重启后 marker 和清理结果写入 `evidence/postgres-check.txt`，不得写入密码。

```bash
git add evidence/postgres-check.txt
git diff --cached --check
git commit -m "test: verify postgres health and persistence"
```

### Task 5：补齐教学文档和启动说明

**文件：**修改 `README.md`、`plan/learning/03.md`。

- [x] **步骤 1：更新 README。**加入以下可复制流程：

```bash
cp .env.example .env
docker compose up -d --wait --wait-timeout 90
docker compose ps
docker compose exec -T postgres pg_isready -U market_dashboard -d market_dashboard
uv run --with duckdb python scripts/check_source_data.py \
  --data-root /mnt/glusterfs/quantdata/tushare \
  --stock-pool config/stock_pool.csv
```

同时说明：首次启动之前检查 5432 的占用情况，按任务 4 的顺序停止并恢复 `stock-market-postgres`；`docker compose down` 保留 volume；`docker compose down -v` 会删除数据库数据，Issue 02 验收时禁止使用；`.env` 是本地开发文件；当前 Compose 只提供数据库环境，Issue 03 才建表和导入。示例凭据只用于本机开发。

- [x] **步骤 2：修订数据源笔记。**保留 `plan/learning/03.md` 路径和原始字段说明，标题改成“课程规划 Issue 02：数据源确认与股票池配置（原学习步骤 03）”，补充：

  - 20 只股票 CSV 的固定性和五行业各 4 只；
  - `stock_list`、日线、分钟数据的实际字段和 `date=YYYY-MM-DD` 分区；
  - 检查脚本命令和“共同覆盖日期最大值”的定义，说明记录存在不等于逐分钟无缺失；
  - 验收结果引用 `evidence/source-check.txt`，不把静态历史数据称为实时数据。

将旧笔记中的分支名、提交文件清单和 PR 说明更新为本计划；原来写成“已检查”的语句必须对应真实命令输出。删除将课程编号当作 GitHub 编号的用法，PR 的关闭引用使用新建任务的实际编号。

- [x] **步骤 3：检查文档和提交。**

```bash
git diff --check
git add README.md plan/learning/03.md
git commit -m "docs: document data environment workflow"
```

### Task 6：最终验收、工作区检查和人工 PR

- [ ] **步骤 1：从干净配置重新执行检查。**

```bash
git status --short
docker compose config --quiet
uv run --with duckdb --with pytest pytest tests/test_check_source_data.py -q
uv run --with duckdb python scripts/check_source_data.py \
  --data-root /mnt/glusterfs/quantdata/tushare \
  --stock-pool config/stock_pool.csv --format text
```

预期：测试通过，源数据脚本返回 0，`git status` 只显示计划纳入提交的文件或为空。

- [ ] **步骤 2：核对 Issue 02 验收矩阵。**

  - 20 只代码在 `stock_list` 且 `list_status=L`：`evidence/source-check.txt`；
  - 日线和分钟数据都可查：`evidence/source-check.txt`；
  - Parquet、OHLCV、日期分区可解释：`plan/learning/03.md`；
  - 一条命令启动、客户端连接、健康检查：`README.md` 和 `evidence/postgres-check.txt`；
  - 重启后数据保留：`evidence/postgres-check.txt`；
  - 未提前建表或导入行情：检查提交文件和 Compose 内容。

- [ ] **步骤 3：审查已有规划改动并纳入提交。**

```bash
git diff -- plan/course-issues.md
git add plan/course-issues.md
git diff --cached --check
git commit -m "docs: consolidate course issue roadmap"
```

只提交经核对属于本次规划的内容；不丢弃用户已有改动。若前面任务已提交该文件，不重复创建空提交。

- [ ] **步骤 4：检查提交并推送分支。**

```bash
git diff --check
git log --oneline main..feat/data_environment
git push -u origin feat/data_environment
```

然后由人工创建 PR，正文列出上述验收矩阵、实际命令输出和已知边界，并关联课程规划 Issue 02 的真实 GitHub 编号；AI 不创建或合入 PR。

## 计划自检

- 规划覆盖了数据源字段/路径/分区、20 只股票、Parquet 校验、PostgreSQL 连接、健康检查和持久化六项要求。
- 建表、迁移和导入明确留给 Issue 03，没有把后续范围混入当前任务。
- 所有持久化数据写入命名 volume；验证使用临时表并在结束时删除。
- 端口冲突、现有容器恢复、`.env` 隔离和证据脱敏都有明确步骤。
- 当前工作区已有的 `plan/course-issues.md` 修改不在计划中覆盖，执行时需保留并人工检查 diff。

## 当前执行结果

- 实现分支：`feat/data_environment`，保留并纳入用户已有股票池、学习笔记和课程规划。
- 源数据校验：17 项临时 Parquet 行为测试通过；文本和 JSON 均退出 0；2026-10-09 覆盖 20 只上市股票，各有 241 条分钟记录。记录覆盖不代表分钟无缺口。
- Compose 环境：配置校验、healthy、容器内及宿主机 TCP 连接通过；重启与保留卷的容器重建后标记均保留，测试表删除。
- 环境恢复：本项目容器已移除，命名卷保留；原 `stock-market-postgres` 恢复 running/healthy。
- 文档：README 与学习笔记已补齐，证据保存在 `evidence/`。
- 发布状态：实际 GitHub Issue 创建和分支推送仍需本机完成 `gh auth login`；弹窗选项只确认发布授权，不完成账号登录。PR 创建和合入由人工执行。
