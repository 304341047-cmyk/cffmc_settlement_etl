from decimal import Decimal

from pydantic import BaseModel


class DepositWithdrawal(BaseModel):
    date: str | None = None
    type: str | None = None
    deposit: Decimal | None = None
    withdrawal: Decimal | None = None
    exchange_rate: Decimal | None = None
    account_id: str | None = None
    note: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None


CashFlow = DepositWithdrawal
