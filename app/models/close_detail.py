from decimal import Decimal

from pydantic import BaseModel


class PositionClosed(BaseModel):
    close_date: str | None = None
    invest_unit: str | None = None
    exchange: str | None = None
    trading_code: str | None = None
    product: str | None = None
    instrument: str | None = None
    open_date: str | None = None
    s_h: str | None = None
    b_s: str | None = None
    lots: Decimal | None = None
    pos_open_price: Decimal | None = None
    prev_sttl: Decimal | None = None
    trans_price: Decimal | None = None
    realized_p_l: Decimal | None = None
    premium_received_paid: Decimal | None = None
    account_id: str | None = None

    source_file: str = ""
    raw_payload: str | None = None
    sheet_name: str | None = None
    raw_line_no: int | None = None
    row_hash: str | None = None


CloseDetail = PositionClosed
