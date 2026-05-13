from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CloseDetail(BaseModel):
    trade_date: date
    account_id: str | None = None
    instrument_code: str
    instrument_name: str | None = None
    direction: str | None = None
    volume: int
    open_price: Decimal | None = None
    close_price: Decimal | None = None
    close_pnl: Decimal | None = None
    commission: Decimal | None = None
    source_file: str | None = None
    sheet_name: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None
