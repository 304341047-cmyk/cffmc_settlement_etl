# 结算单 ETL 重构任务记录

记录日期：2026-05-12

## 目标

基于监控中心导出的结算 xlsx，重构本地结算单 ETL。系统需要完整解析、校验、入库并方便后续查询：

- 资金状况表
- 出入金流水表
- 行权明细表
- 持仓明细表
- 持仓汇总表
- 成交汇总表
- 原始成交明细
- FIFO 开平仓匹配
- FIFO 剩余持仓 lot

结算文件本身可能存在重复、缺字段、空列、汇总与明细不一致等问题，因此 ETL 要以可追溯和严格校验为优先。

## 已确认决策

- 在现有项目和表体系上改造，不另起全新工程。
- 当前业务数据库允许重建，不做旧数据迁移。
- 原始成交必须完整入库。
- `trade_no` 不能再作为唯一去重依据，因为同一成交序号可能合法出现买/卖两行。
- 新唯一键优先使用 `source_file + sheet_name + raw_line_no`，必要时加稳定 `row_hash`。
- FIFO 采用额外表记录：
  - 开平仓匹配：`fifo_matches`
  - 剩余持仓 lot：`position_lots`
- 第一份文件或中间缺历史时，用账单期末持仓生成 `seed/adjustment lot`，并记录来源和原因。
- 期权行权暂时只保存明细、费用和校验，不自动推导标的期货 lot。
- 解析 xlsx 时必须按原始表头列位读取，不能压缩空单元格；期权持仓中的空列会影响买/卖持仓方向。
- 异常处理采用严格模式：任一关键校验失败时，该文件业务数据回滚，只保留失败源文件记录和错误信息。
- 成交汇总、持仓汇总采用双轨保存：
  - 保存结算单原始汇总
  - 保存由明细/FIFO 派生的结果
  - 通过校验结果对账
- 底层数据库表用英文名，额外提供中文查询视图。
- 行情 sqlite 通过配置化 SQL 模板接入，xlsx 缺结算价时才查行情库。

## 待实现变更

### 配置

新增配置项：

- `SETTLEMENT_DB_PATH`
- `MARKET_DB_PATH`
- `MARKET_SETTLEMENT_QUERY`

统一数据库路径，避免 `db/trading.db` 和 `app/db/trading.db` 分叉。

### ORM/Pydantic 模型

改造或新增以下数据结构：

- `TradeExecution`
  - 增加 `sheet_name`
  - 增加 `raw_line_no`
  - 增加 `row_hash`
  - 唯一键改为源文件行级 identity
- `CashFlow`
- `TradeSummary`
- `CloseDetail`
- `FifoMatch`
- `PositionLot`
- `ValidationIssue`

保留并强化：

- `AccountDailySnapshot`
- `OptionExerciseDetail`
- `PositionDetail`
- `PositionSnapshot`
- `SourceFile`

### 解析器

重写或大幅整理 `CFFMCSettlementParser`：

- 删除重复定义的同名方法，避免后定义覆盖前定义。
- 解析 sheet：
  - `客户交易结算日报`
  - `成交明细`
  - `平仓明细`
  - `持仓明细`
  - `期权成交明细`
- 解析日报内区块：
  - `期货期权账户资金状况`
  - `期货期权账户出入金明细`
  - `其它资金明细`
  - `期货成交汇总`
  - `期货持仓汇总`
  - `期权成交汇总`
  - `期权持仓汇总`
  - `期权行权明细`
- 所有表格读取按标题行定位，再按表头列名映射原始列位。

### FIFO

FIFO 处理规则：

- 按 `trade_date + trade_time + raw_line_no` 排序。
- 买开生成 long lot，卖开生成 short lot。
- 卖平消耗 long lot。
- 买平消耗 short lot。
- 对无法从历史成交推导出的期末持仓，生成 `seed/adjustment lot`。
- 期末 FIFO lot 数量必须和账单持仓汇总一致，否则文件失败。

### 校验

必须覆盖：

- 期货手续费 + 期权手续费 + 行权手续费 = 当日手续费。
- 明细派生成交汇总 = 账单成交汇总。
- FIFO 期末持仓 = 账单持仓汇总。
- xlsx 有结算价时不用行情库。
- xlsx 缺结算价时查行情库。
- xlsx 与行情库都缺结算价时失败。

### 入库

- `save_to_db` 改成单文件事务。
- 业务数据全部成功才 commit。
- 失败时 rollback，并记录 `source_files.status = failed`。
- 重跑同一文件按 file hash 跳过，或按 row identity 保持幂等。
- 建立中文视图：
  - `资金状况表`
  - `出入金流水表`
  - `行权明细表`
  - `持仓明细表`
  - `持仓汇总表`
  - `成交汇总表`

## 样例文件与已知事实

现有样例：

- `data/inbox/016081183126_2026-04-16.xlsx`
- `data/inbox/016081183126_2026-04-17.xlsx`
- `data/inbox/016081183126_2026-04-24.xlsx`

已观察到：

- 三份文件 sheet 名一致。
- 2026-04-16 的 `成交明细` 中，成交序号 `000000000104991510` 同时有买平和卖平两行，必须都入库。
- 2026-04-17 有多组类似重复成交序号，不能误删。
- 2026-04-24 有出金流水，金额为 `100000`。
- 期权持仓汇总中买/卖持仓依赖空列位置，不能将行内容压缩后再读。
- 当前 `app/db/trading.db` 是空文件，根目录 `db` 目前未发现实际业务库。

## 明天建议执行顺序

1. 先清理/确认 `__pycache__` 等非源码改动，不纳入本次提交。
2. 扩展 `app/models` 和 `app/db/models.py`。
3. 统一 `app/config.py` 与 `app/db/base.py` 的数据库路径。
4. 重写 `CFFMCSettlementParser` 的表格读取工具和各区块解析。
5. 实现 FIFO 生成 `fifo_matches` 与 `position_lots`。
6. 实现严格校验和 `validation_issues`。
7. 改造 `app/db_writer.py` 为单文件事务写入。
8. 用三份样例跑解析计数和入库回归。
9. 检查中文视图是否能直接查询六张业务表。

## 回归验收清单

- 2026-04-16 原始成交行数不因重复成交序号减少。
- 2026-04-17 多组重复成交序号均保留。
- 2026-04-24 出入金流水解析出 withdrawal `100000`。
- 三份文件手续费校验通过。
- FIFO 期末持仓与账单持仓汇总一致。
- 任一关键校验失败时，业务表没有半截入库。

## 2026-05-13 进度

- 已新增并接入配置：
  - `SETTLEMENT_DB_PATH`
  - `MARKET_DB_PATH`
  - `MARKET_SETTLEMENT_QUERY`
- `MARKET_DB_PATH` 默认值已设为：`D:\CodeProjects\futures_exchange_daily_data\data\futures_daily.sqlite`。
- `app/db/base.py` 已统一使用 `app.config.DB_PATH`，避免 `db/trading.db` 与 `app/db/trading.db` 分叉。
- `TradeExecution` 与 `trade_executions` 已增加：
  - `sheet_name`
  - `raw_line_no`
  - `row_hash`
- `trade_executions` 唯一键已改为 `source_file + sheet_name + raw_line_no + row_hash`，不再按 `trade_no` 去重。
- 已新增 Pydantic/ORM 结构：
  - `CashFlow`
  - `TradeSummary`
  - `CloseDetail`
  - `FifoMatch`
  - `PositionLot`
  - `ValidationIssue`
- `save_to_db` 已改为单事务写入，并覆盖新增业务表。
- 已新增中文查询视图创建函数，并在启动建表后创建：
  - `资金状况表`
  - `出入金流水表`
  - `行权明细表`
  - `持仓明细表`
  - `持仓汇总表`
  - `成交汇总表`
- `CFFMCSettlementParser` 已为期货/期权成交行生成 `raw_line_no` 与 `row_hash`。
- 已新增日报内 `期货期权账户出入金明细` 解析，目标覆盖 2026-04-24 withdrawal `100000`。
- 已新增最小可用 FIFO 处理器：
  - 买开生成 long lot
  - 卖开生成 short lot
  - 卖平消耗 long lot
  - 买平消耗 short lot
  - 缺历史时生成 seed lot
  - 期末账单持仓不足部分生成 adjustment lot
  - 无法对齐时生成 `ValidationIssue`

### 当前未完成/待验证

- 当前 shell 环境没有可用 `python` / `py` 命令，尚未能运行三份样例回归。
- `TradeSummary`、`CloseDetail` 的具体解析还未接入。
- 严格失败模式尚未把 blocking `ValidationIssue` 自动升级为整文件失败。
- 行情 sqlite 查询逻辑已配置化，但尚未接入结算价补全流程；等待行情库补全后继续验证。
