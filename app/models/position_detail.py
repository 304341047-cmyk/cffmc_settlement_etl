from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class PositionDetail(BaseModel):
    trade_date: date
    account_id: str | None = None
    instrument_code: str
    instrument_name: str | None = None
    asset_type: str | None = None
    direction: str | None = None
    open_interest: int
    avg_open_price: Decimal | None = None
    settlement_price: Decimal | None = None
    yesterday_settlement_price: Decimal | None = None
    margin_occupied: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    source_file: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None