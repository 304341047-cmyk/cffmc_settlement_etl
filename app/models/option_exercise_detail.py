from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class OptionExerciseDetail(BaseModel):
    """
    期权行权/履约明细层：
    从“客户交易结算日报”底部相关区块提取。
    """
    trade_date: date
    account_id: str | None = None

    exchange: str | None = None
    instrument_code: str | None = None
    underlying: str | None = None
    direction: str | None = None
    exercise_type: str | None = None
    quantity: int | None = None

    price: Decimal | None = None
    amount: Decimal | None = None
    commission: Decimal | None = None

    source_file: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None