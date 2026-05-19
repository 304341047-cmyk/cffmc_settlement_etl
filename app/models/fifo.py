from decimal import Decimal

from pydantic import BaseModel


class FifoMatch(BaseModel):
    date: str | None = None
    account_id: str | None = None
    instrument: str
    b_s: str
    open_trade_row_hash: str | None = None
    close_trade_row_hash: str | None = None
    lots: Decimal
    open_price: Decimal | None = None
    close_price: Decimal | None = None
    realized_p_l: Decimal | None = None
    source_file: str = ""


class PositionLot(BaseModel):
    date: str | None = None
    account_id: str | None = None
    instrument: str
    b_s: str
    lots: Decimal
    remaining_volume: Decimal
    pos_open_price: Decimal | None = None
    open_time: str | None = None
    source_file: str = ""
    source_type: str = "trade"
    source_reason: str | None = None
    open_trade_row_hash: str | None = None
