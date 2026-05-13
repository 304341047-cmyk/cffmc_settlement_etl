from sqlalchemy import Boolean, Column, Integer, String, Date, DateTime, Numeric, UniqueConstraint
from datetime import datetime
from app.db.base import Base


class TradeExecutionDB(Base):
    __tablename__ = "trade_executions"
    __table_args__ = (
        UniqueConstraint("source_file", "sheet_name", "raw_line_no", "row_hash", name="uix_trade_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    instrument_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)
    market = Column(String, nullable=True)
    direction = Column(String, nullable=False)
    open_close = Column(String, nullable=True)
    volume = Column(Integer, nullable=False)
    price = Column(Numeric(18, 4), nullable=False)
    turnover = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    trade_time = Column(DateTime, nullable=True)
    trade_no = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    sheet_name = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)


class CashFlowDB(Base):
    __tablename__ = "cash_flows"
    __table_args__ = (
        UniqueConstraint("source_file", "source_section", "raw_line_no", "row_hash", name="uix_cash_flow_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    flow_type = Column(String, nullable=False)
    amount = Column(Numeric(18, 4), nullable=False)
    currency = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)


class TradeSummaryDB(Base):
    __tablename__ = "trade_summaries"
    __table_args__ = (
        UniqueConstraint(
            "source_file",
            "source_section",
            "raw_line_no",
            "row_hash",
            name="uix_trade_summary_source_row",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    instrument_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)
    direction = Column(String, nullable=True)
    open_close = Column(String, nullable=True)
    volume = Column(Integer, nullable=False, default=0)
    turnover = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)


class CloseDetailDB(Base):
    __tablename__ = "close_details"
    __table_args__ = (
        UniqueConstraint("source_file", "sheet_name", "raw_line_no", "row_hash", name="uix_close_detail_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    instrument_name = Column(String, nullable=True)
    direction = Column(String, nullable=True)
    volume = Column(Integer, nullable=False)
    open_price = Column(Numeric(18, 4), nullable=True)
    close_price = Column(Numeric(18, 4), nullable=True)
    close_pnl = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=True)
    sheet_name = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)


class PositionDetailDB(Base):
    """
    原始持仓明细层：
    - 期货来自“持仓明细”sheet
    - 期权来自“客户交易结算日报”中的“期权持仓汇总”
    """
    __tablename__ = "position_details"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "trade_date",
            "instrument_code",
            "direction",
            "source_file",
            "source_section",
            "raw_line_no",
            name="uix_position_detail",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    instrument_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)                  # futures / option
    direction = Column(String, nullable=True)                   # long / short
    open_interest = Column(Integer, nullable=False)
    avg_open_price = Column(Numeric(18, 4), nullable=True)
    settlement_price = Column(Numeric(18, 4), nullable=True)
    yesterday_settlement_price = Column(Numeric(18, 4), nullable=True)
    margin_occupied = Column(Numeric(18, 4), nullable=True)
    unrealized_pnl = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=True)
    source_section = Column(String, nullable=True)              # 持仓明细 / 期权持仓汇总
    raw_line_no = Column(Integer, nullable=True)


class PositionSnapshotDB(Base):
    """
    日终持仓快照层：
    由 position_details 聚合生成
    """
    __tablename__ = "position_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "trade_date", "instrument_code", "direction", name="uix_position"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    instrument_name = Column(String, nullable=True)
    asset_type = Column(String, nullable=True)
    direction = Column(String, nullable=True)
    open_interest = Column(Integer, nullable=False)
    yesterday_open_interest = Column(Integer, nullable=True)
    avg_open_price = Column(Numeric(18, 4), nullable=True)
    settlement_price = Column(Numeric(18, 4), nullable=True)
    realized_pnl = Column(Numeric(18, 4), nullable=True)
    unrealized_pnl = Column(Numeric(18, 4), nullable=True)
    option_pnl = Column(Numeric(18, 4), nullable=True)
    margin_occupied = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=True)


class AccountDailySnapshotDB(Base):
    __tablename__ = "account_daily_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    broker = Column(String, nullable=True)

    # ===== 兼容旧字段 =====
    begin_client_equity = Column(Numeric(18, 4), nullable=True)   # 兼容旧逻辑，等于 begin_balance
    end_client_equity = Column(Numeric(18, 4), nullable=True)     # 对应当日结存

    # ===== 原始日报字段 =====
    begin_balance = Column(Numeric(18, 4), nullable=True)         # 上日结存
    deposit = Column(Numeric(18, 4), nullable=True)               # 入金
    withdrawal = Column(Numeric(18, 4), nullable=True)            # 出金
    premium = Column(Numeric(18, 4), nullable=True)               # 当日总权利金
    non_fx_pledge = Column(Numeric(18, 4), nullable=True)         # 非货币充抵金额
    fx_pledge = Column(Numeric(18, 4), nullable=True)             # 货币充抵金额
    frozen_cash = Column(Numeric(18, 4), nullable=True)           # 冻结资金
    margin_call = Column(Numeric(18, 4), nullable=True)           # 追加保证金

    # ===== 资金/风险相关 =====
    available_fund = Column(Numeric(18, 4), nullable=True)
    margin_occupied = Column(Numeric(18, 4), nullable=True)
    realized_pnl = Column(Numeric(18, 4), nullable=True)
    unrealized_pnl = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    option_commission = Column(Numeric(18, 4), nullable=True)
    exercise_commission = Column(Numeric(18, 4), nullable=True)
    risk_degree = Column(Numeric(18, 6), nullable=True)

    source_file = Column(String, nullable=True)


class SourceFileDB(Base):
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    parser_name = Column(String, nullable=True)
    status = Column(String, nullable=False)   # success / failed
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FifoMatchDB(Base):
    __tablename__ = "fifo_matches"
    __table_args__ = (
        UniqueConstraint(
            "source_file",
            "open_trade_row_hash",
            "close_trade_row_hash",
            "volume",
            name="uix_fifo_match",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    asset_type = Column(String, nullable=True)
    direction = Column(String, nullable=False)
    open_trade_row_hash = Column(String, nullable=True)
    close_trade_row_hash = Column(String, nullable=True)
    volume = Column(Integer, nullable=False)
    open_price = Column(Numeric(18, 4), nullable=True)
    close_price = Column(Numeric(18, 4), nullable=True)
    realized_pnl = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=True)


class PositionLotDB(Base):
    __tablename__ = "position_lots"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "account_id",
            "instrument_code",
            "direction",
            "source_file",
            "open_trade_row_hash",
            name="uix_position_lot",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)
    instrument_code = Column(String, nullable=False)
    asset_type = Column(String, nullable=True)
    direction = Column(String, nullable=False)
    volume = Column(Integer, nullable=False)
    remaining_volume = Column(Integer, nullable=False)
    open_price = Column(Numeric(18, 4), nullable=True)
    open_time = Column(DateTime, nullable=True)
    source_file = Column(String, nullable=True)
    source_type = Column(String, nullable=False, default="trade")
    source_reason = Column(String, nullable=True)
    open_trade_row_hash = Column(String, nullable=True)


class ValidationIssueDB(Base):
    __tablename__ = "validation_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    check_name = Column(String, nullable=False)
    severity = Column(String, nullable=False, default="error")
    message = Column(String, nullable=False)
    expected_value = Column(String, nullable=True)
    actual_value = Column(String, nullable=True)
    is_blocking = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class OptionExerciseDetailDB(Base):
    """
    期权行权/履约明细层：
    从“客户交易结算日报”底部相关区块提取。
    """
    __tablename__ = "option_exercise_details"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "trade_date",
            "exchange",
            "instrument_code",
            "direction",
            "quantity",
            "source_file",
            "raw_line_no",
            name="uix_option_exercise_detail",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False)
    account_id = Column(String, nullable=True)

    exchange = Column(String, nullable=True)               # 交易所，如 大连商品交易所
    instrument_code = Column(String, nullable=True)        # 期权合约
    underlying = Column(String, nullable=True)             # 标的合约
    direction = Column(String, nullable=True)              # long / short / buy / sell（先预留）
    exercise_type = Column(String, nullable=True)          # 行权 / 被行权 / 履约 等
    quantity = Column(Integer, nullable=True)

    price = Column(Numeric(18, 4), nullable=True)
    amount = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)

    source_file = Column(String, nullable=True)
    source_section = Column(String, nullable=True)         # 行权明细 / 履约明细
    raw_line_no = Column(Integer, nullable=True)
