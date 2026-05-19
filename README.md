# Settlement ETL

监控中心导出的结算单 ETL。当前项目字段口径已对齐 `ctp_settlement_etl`，但本项目额外做真实成交 FIFO 推导，用来和账单持仓做严格对账。

## 日常流程

1. 把同一账户、从 0 持仓起点开始的结算单 `.xlsx` 放到 `data/inbox/`。
2. 在 `cmd.exe` 里运行：

```cmd
C:\Users\30434\anaconda3\python.exe -B -m app.main
```

3. 成功文件会进入 `data/archive/yyyy-MM/`。
4. 失败文件会进入 `data/error/`，原因看 `logs/app.log` 和 `validation_result`。
5. SQLite 数据库默认在 `db/trading.db`。

建议新账户尽量从 0 持仓日期开始导入。严格 FIFO 不会用 seed/adjustment 自动调平；如果首日已有持仓但缺历史成交，会暴露为对账失败。

## 重建数据库

如果确认当前数据可以重建，先删除库，再重新跑 inbox 文件：

```cmd
if exist db\trading.db del /f db\trading.db
C:\Users\30434\anaconda3\python.exe -B -m app.main
```

如果文件已经在 archive，需要先把要重跑的文件复制回 `data/inbox/`，或用临时脚本从 archive 解析入库。

## 主要数据表

CTP 统一口径表：

- `account_summary`: 资金状况
- `deposit_withdrawal`: 出入金流水
- `transaction_record`: 原始成交明细
- `exercise_statement`: 行权明细
- `position_closed`: 平仓明细
- `positions_detail`: 账单持仓明细
- `positions`: 账单持仓汇总
- `validation_result`: 校验结果
- `source_file_record`: 源文件处理记录

FIFO 扩展表：

- `fifo_matches`: FIFO 开平匹配
- `position_lots`: 每日 FIFO 剩余 lot
- `fifo_positions`: FIFO 推导持仓汇总

## 快速检查

查看处理状态：

```cmd
C:\Users\30434\anaconda3\python.exe -B -c "import sqlite3,json; conn=sqlite3.connect('db/trading.db'); print(json.dumps(conn.execute('select process_status,count(*) from source_file_record group by process_status').fetchall(), ensure_ascii=False, indent=2))"
```

查看账户日期范围：

```cmd
C:\Users\30434\anaconda3\python.exe -B -c "import sqlite3,json; conn=sqlite3.connect('db/trading.db'); print(json.dumps(conn.execute('select account_id,min(date_from),max(date_to),count(*) from account_summary group by account_id').fetchall(), ensure_ascii=False, indent=2))"
```

查看是否有阻断失败：

```cmd
C:\Users\30434\anaconda3\python.exe -B -c "import sqlite3,json; conn=sqlite3.connect('db/trading.db'); print(json.dumps(conn.execute('select source_file,check_name,status,details from validation_result where is_blocking=1 order by source_file,id').fetchall(), ensure_ascii=False, indent=2))"
```

检查账单持仓和 FIFO 持仓是否每日对齐。严格对账失败会写入 `validation_result`，所以这条为空就是主验收通过：

```cmd
C:\Users\30434\anaconda3\python.exe -B -c "import sqlite3,json; conn=sqlite3.connect('db/trading.db'); rows=conn.execute('select source_file,date,account_id,details,expected_value,actual_value from validation_result where check_name=? and status=? order by source_file,id', ('fifo_position_reconcile','FAIL')).fetchall(); print(json.dumps(rows, ensure_ascii=False, indent=2))"
```

查看每日 `position_lots` 和 `fifo_positions` 的总量是否一致：

```cmd
C:\Users\30434\anaconda3\python.exe -B -c "import sqlite3,json; conn=sqlite3.connect('db/trading.db'); rows=conn.execute('select l.date,l.lot_sum,f.pos_sum,l.lot_sum-f.pos_sum as diff from (select date,sum(remaining_volume) lot_sum from position_lots group by date) l join (select date,sum(lots) pos_sum from fifo_positions group by date) f on l.date=f.date order by l.date').fetchall(); print(json.dumps(rows, ensure_ascii=False, indent=2))"
```

## 当前 9277 验收基线

当前 `db/trading.db` 已用 9277 账户完整批次重建：

- `source_file_record`: 15 个 `SUCCESS`
- 日期范围：`20260413` 到 `20260506`
- `20260413`: 0 持仓
- `transaction_record`: 95 条
- `positions`: 47 条
- `fifo_positions`: 47 条
- blocking validation: 0

## 常见问题

- `python` / `py` 不在 PATH：直接用 `C:\Users\30434\anaconda3\python.exe`。
- `cmd.exe` 中文显示乱码：先运行 `chcp 65001`，或者直接在 VSCode 里看输出文件/README。
- 归档失败或 inbox 残留：如果 archive 中已有同名同 MD5 文件，可以删除 inbox 副本；当前移动逻辑遇到同名目标会自动加后缀。
- 新账户首日不是 0 持仓：严格 FIFO 很可能失败，这是预期行为。优先找到更早的 0 持仓起点再导入。
- 只想看日志：打开 `logs/app.log`。
