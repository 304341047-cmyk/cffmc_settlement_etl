from decimal import Decimal

from pydantic import BaseModel


class Positions(BaseModel):
    date: str | None = None
    invest_unit: str | None = None
    trading_code: str | None = None
    product: str | None = None
    instrument: str | None = None
    long_pos: Decimal | None = None
    avg_buy_price: Decimal | None = None
    short_pos: Decimal | None = None
    avg_sell_price: Decimal | None = None
    prev_sttl: Decimal | None = None
    sttl_today: Decimal | None = None
    mtm_p_l: Decimal | None = None
    margin_occupied: Decimal | None = None
    s_h: str | None = None
    market_value_long: Decimal | None = None
    market_value_short: Decimal | None = None
    account_id: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None


class FifoPosition(BaseModel):
    date: str | None = None
    account_id: str | None = None
    instrument: str
    b_s: str
    lots: Decimal
    avg_open_price: Decimal | None = None
    source_file: str = ""


PositionSnapshot = Positions
