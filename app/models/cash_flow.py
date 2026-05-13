from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CashFlow(BaseModel):
    trade_date: date
    account_id: str | None = None
    flow_type: str
    amount: Decimal
    currency: str | None = None
    summary: str | None = None
    source_file: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None
