from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TradeSummary(BaseModel):
    trade_date: date
    account_id: str | None = None
    instrument_code: str
    instrument_name: str | None = None
    asset_type: str | None = None
    direction: str | None = None
    open_close: str | None = None
    volume: int = 0
    turnover: Decimal | None = None
    commission: Decimal | None = None
    source_file: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None
