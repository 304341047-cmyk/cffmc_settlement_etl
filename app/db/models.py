from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, Numeric, String, Text, UniqueConstraint

from app.db.base import Base


class AccountSummaryDB(Base):
    __tablename__ = "account_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    creation_date = Column(String, nullable=True)
    date_from = Column(String, nullable=True)
    date_to = Column(String, nullable=True)
    client_id = Column(String, nullable=True)
    client_name = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    currency = Column(String, nullable=True)

    balance_b_f = Column(Numeric(18, 4), nullable=True)
    deposit_withdrawal = Column(Numeric(18, 4), nullable=True)
    realized_p_l = Column(Numeric(18, 4), nullable=True)
    mtm_p_l = Column(Numeric(18, 4), nullable=True)
    exercise_p_l = Column(Numeric(18, 4), nullable=True)
    commission = Column(Numeric(18, 4), nullable=True)
    exercise_fee = Column(Numeric(18, 4), nullable=True)
    delivery_fee = Column(Numeric(18, 4), nullable=True)
    new_fx_pledge = Column(Numeric(18, 4), nullable=True)
    fx_redemption = Column(Numeric(18, 4), nullable=True)
    chg_in_pledge_amt = Column(Numeric(18, 4), nullable=True)
    premium_received = Column(Numeric(18, 4), nullable=True)
    premium_paid = Column(Numeric(18, 4), nullable=True)
    delivery_p_l = Column(Numeric(18, 4), nullable=True)

    initial_margin = Column(Numeric(18, 4), nullable=True)
    balance_c_f = Column(Numeric(18, 4), nullable=True)
    pledge_amount = Column(Numeric(18, 4), nullable=True)
    client_equity = Column(Numeric(18, 4), nullable=True)
    fx_pledge_occ = Column(Numeric(18, 4), nullable=True)
    margin_occupied = Column(Numeric(18, 4), nullable=True)
    delivery_margin = Column(Numeric(18, 4), nullable=True)
    market_value_long = Column(Numeric(18, 4), nullable=True)
    market_value_short = Column(Numeric(18, 4), nullable=True)
    market_value_equity = Column(Numeric(18, 4), nullable=True)
    fund_avail = Column(Numeric(18, 4), nullable=True)
    risk_degree = Column(Numeric(18, 6), nullable=True)
    margin_call = Column(Numeric(18, 4), nullable=True)
    chg_in_fx_pledge = Column(Numeric(18, 4), nullable=True)

    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DepositWithdrawalDB(Base):
    __tablename__ = "deposit_withdrawal"
    __table_args__ = (
        UniqueConstraint("source_file", "raw_line_no", "row_hash", name="uix_deposit_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    type = Column(String, nullable=True)
    deposit = Column(Numeric(18, 4), nullable=True)
    withdrawal = Column(Numeric(18, 4), nullable=True)
    exchange_rate = Column(Numeric(18, 8), nullable=True)
    account_id = Column(String, nullable=True)
    note = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TransactionRecordDB(Base):
    __tablename__ = "transaction_record"
    __table_args__ = (
        UniqueConstraint("source_file", "sheet_name", "raw_line_no", "row_hash", name="uix_transaction_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    invest_unit = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    trading_code = Column(String, nullable=True)
    product = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    b_s = Column(String, nullable=True)
    s_h = Column(String, nullable=True)
    price = Column(Numeric(18, 4), nullable=True)
    lots = Column(Numeric(18, 4), nullable=True)
    turnover = Column(Numeric(18, 4), nullable=True)
    o_c = Column(String, nullable=True)
    fee = Column(Numeric(18, 4), nullable=True)
    realized_p_l = Column(Numeric(18, 4), nullable=True)
    premium_received_paid = Column(Numeric(18, 4), nullable=True)
    trans_no = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    sheet_name = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    trade_time = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ExerciseStatementDB(Base):
    __tablename__ = "exercise_statement"
    __table_args__ = (
        UniqueConstraint("source_file", "source_section", "raw_line_no", "row_hash", name="uix_exercise_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    invest_unit = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    trading_code = Column(String, nullable=True)
    product = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    b_s = Column(String, nullable=True)
    strike_price = Column(Numeric(18, 4), nullable=True)
    exercise_price = Column(Numeric(18, 4), nullable=True)
    lots = Column(Numeric(18, 4), nullable=True)
    turnover = Column(Numeric(18, 4), nullable=True)
    exercise_p_l = Column(Numeric(18, 4), nullable=True)
    exercise_fee = Column(Numeric(18, 4), nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PositionClosedDB(Base):
    __tablename__ = "position_closed"
    __table_args__ = (
        UniqueConstraint("source_file", "sheet_name", "raw_line_no", "row_hash", name="uix_position_closed_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    close_date = Column(String, nullable=True)
    invest_unit = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    trading_code = Column(String, nullable=True)
    product = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    open_date = Column(String, nullable=True)
    s_h = Column(String, nullable=True)
    b_s = Column(String, nullable=True)
    lots = Column(Numeric(18, 4), nullable=True)
    pos_open_price = Column(Numeric(18, 4), nullable=True)
    prev_sttl = Column(Numeric(18, 4), nullable=True)
    trans_price = Column(Numeric(18, 4), nullable=True)
    realized_p_l = Column(Numeric(18, 4), nullable=True)
    premium_received_paid = Column(Numeric(18, 4), nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    sheet_name = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PositionsDetailDB(Base):
    __tablename__ = "positions_detail"
    __table_args__ = (
        UniqueConstraint("source_file", "source_section", "raw_line_no", "row_hash", "b_s", name="uix_positions_detail_source_row"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    invest_unit = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    trading_code = Column(String, nullable=True)
    product = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    open_date = Column(String, nullable=True)
    s_h = Column(String, nullable=True)
    b_s = Column(String, nullable=True)
    position_qty = Column(Numeric(18, 4), nullable=True)
    pos_open_price = Column(Numeric(18, 4), nullable=True)
    prev_sttl = Column(Numeric(18, 4), nullable=True)
    settlement_price = Column(Numeric(18, 4), nullable=True)
    accum_p_l = Column(Numeric(18, 4), nullable=True)
    mtm_p_l = Column(Numeric(18, 4), nullable=True)
    margin = Column(Numeric(18, 4), nullable=True)
    market_value = Column(Numeric(18, 4), nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PositionsDB(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("source_file", "date", "account_id", "instrument", name="uix_positions_daily"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    invest_unit = Column(String, nullable=True)
    trading_code = Column(String, nullable=True)
    product = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    long_pos = Column(Numeric(18, 4), nullable=True)
    avg_buy_price = Column(Numeric(18, 4), nullable=True)
    short_pos = Column(Numeric(18, 4), nullable=True)
    avg_sell_price = Column(Numeric(18, 4), nullable=True)
    prev_sttl = Column(Numeric(18, 4), nullable=True)
    sttl_today = Column(Numeric(18, 4), nullable=True)
    mtm_p_l = Column(Numeric(18, 4), nullable=True)
    margin_occupied = Column(Numeric(18, 4), nullable=True)
    s_h = Column(String, nullable=True)
    market_value_long = Column(Numeric(18, 4), nullable=True)
    market_value_short = Column(Numeric(18, 4), nullable=True)
    account_id = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    raw_payload = Column(Text, nullable=True)
    source_section = Column(String, nullable=True)
    raw_line_no = Column(Integer, nullable=True)
    row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FifoMatchDB(Base):
    __tablename__ = "fifo_matches"
    __table_args__ = (
        UniqueConstraint("source_file", "open_trade_row_hash", "close_trade_row_hash", "lots", name="uix_fifo_match"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    instrument = Column(String, nullable=False)
    b_s = Column(String, nullable=False)
    open_trade_row_hash = Column(String, nullable=True)
    close_trade_row_hash = Column(String, nullable=True)
    lots = Column(Numeric(18, 4), nullable=False)
    open_price = Column(Numeric(18, 4), nullable=True)
    close_price = Column(Numeric(18, 4), nullable=True)
    realized_p_l = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PositionLotDB(Base):
    __tablename__ = "position_lots"
    __table_args__ = (
        UniqueConstraint("date", "account_id", "instrument", "b_s", "source_file", "open_trade_row_hash", name="uix_position_lot"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    instrument = Column(String, nullable=False)
    b_s = Column(String, nullable=False)
    lots = Column(Numeric(18, 4), nullable=False)
    remaining_volume = Column(Numeric(18, 4), nullable=False)
    pos_open_price = Column(Numeric(18, 4), nullable=True)
    open_time = Column(String, nullable=True)
    source_file = Column(String, nullable=False)
    source_type = Column(String, nullable=False, default="trade")
    source_reason = Column(String, nullable=True)
    open_trade_row_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class FifoPositionDB(Base):
    __tablename__ = "fifo_positions"
    __table_args__ = (
        UniqueConstraint("source_file", "date", "account_id", "instrument", "b_s", name="uix_fifo_positions_daily"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    instrument = Column(String, nullable=False)
    b_s = Column(String, nullable=False)
    lots = Column(Numeric(18, 4), nullable=False)
    avg_open_price = Column(Numeric(18, 4), nullable=True)
    source_file = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ValidationResultDB(Base):
    __tablename__ = "validation_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    check_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    actual_value = Column(String, nullable=True)
    expected_value = Column(String, nullable=True)
    diff_value = Column(String, nullable=True)
    tolerance = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    source_file = Column(String, nullable=False)
    date = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    is_blocking = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SourceFileRecordDB(Base):
    __tablename__ = "source_file_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String, nullable=False)
    file_md5 = Column(String, nullable=False, unique=True)
    parser_name = Column(String, nullable=True)
    process_status = Column(String, nullable=False, default="SUCCESS")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
