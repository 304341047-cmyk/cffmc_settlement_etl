from decimal import Decimal

from pydantic import BaseModel


class TransactionRecord(BaseModel):
    date: str | None = None
    invest_unit: str | None = None
    exchange: str | None = None
    trading_code: str | None = None
    product: str | None = None
    instrument: str | None = None
    b_s: str | None = None
    s_h: str | None = None
    price: Decimal | None = None
    lots: Decimal | None = None
    turnover: Decimal | None = None
    o_c: str | None = None
    fee: Decimal | None = None
    realized_p_l: Decimal | None = None
    premium_received_paid: Decimal | None = None
    trans_no: str | None = None
    account_id: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    sheet_name: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None
    trade_time: str | None = None


TradeExecution = TransactionRecord
