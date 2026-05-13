from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class FifoMatch(BaseModel):
    trade_date: date
    account_id: str | None = None
    instrument_code: str
    asset_type: str | None = None
    direction: str
    open_trade_row_hash: str | None = None
    close_trade_row_hash: str | None = None
    volume: int
    open_price: Decimal | None = None
    close_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    source_file: str | None = None


class PositionLot(BaseModel):
    trade_date: date
    account_id: str | None = None
    instrument_code: str
    asset_type: str | None = None
    direction: str
    volume: int
    remaining_volume: int
    open_price: Decimal | None = None
    open_time: datetime | None = None
    source_file: str | None = None
    source_type: str = "trade"
    source_reason: str | None = None
    open_trade_row_hash: str | None = None
