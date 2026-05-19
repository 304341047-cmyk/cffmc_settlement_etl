from decimal import Decimal

from pydantic import BaseModel


class PositionsDetail(BaseModel):
    date: str | None = None
    invest_unit: str | None = None
    exchange: str | None = None
    trading_code: str | None = None
    product: str | None = None
    instrument: str | None = None
    open_date: str | None = None
    s_h: str | None = None
    b_s: str | None = None
    position_qty: Decimal | None = None
    pos_open_price: Decimal | None = None
    prev_sttl: Decimal | None = None
    settlement_price: Decimal | None = None
    accum_p_l: Decimal | None = None
    mtm_p_l: Decimal | None = None
    margin: Decimal | None = None
    market_value: Decimal | None = None
    account_id: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    source_section: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None


PositionDetail = PositionsDetail
