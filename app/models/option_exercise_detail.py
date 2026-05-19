from decimal import Decimal

from pydantic import BaseModel


class ExerciseStatement(BaseModel):
    date: str | None = None
    invest_unit: str | None = None
    exchange: str | None = None
    trading_code: str | None = None
    product: str | None = None
    instrument: str | None = None
    b_s: str | None = None
    strike_price: Decimal | None = None
    exercise_price: Decimal | None = None
    lots: Decimal | None = None
    turnover: Decimal | None = None
    exercise_p_l: Decimal | None = None
    exercise_fee: Decimal | None = None
    account_id: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None


OptionExerciseDetail = ExerciseStatement
