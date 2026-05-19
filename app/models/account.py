from decimal import Decimal

from pydantic import BaseModel


class AccountSummary(BaseModel):
    creation_date: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    client_id: str | None = None
    client_name: str | None = None
    account_id: str | None = None
    currency: str | None = None

    balance_b_f: Decimal | None = None
    deposit_withdrawal: Decimal | None = None
    realized_p_l: Decimal | None = None
    mtm_p_l: Decimal | None = None
    exercise_p_l: Decimal | None = None
    commission: Decimal | None = None
    exercise_fee: Decimal | None = None
    delivery_fee: Decimal | None = None
    new_fx_pledge: Decimal | None = None
    fx_redemption: Decimal | None = None
    chg_in_pledge_amt: Decimal | None = None
    premium_received: Decimal | None = None
    premium_paid: Decimal | None = None
    delivery_p_l: Decimal | None = None

    initial_margin: Decimal | None = None
    balance_c_f: Decimal | None = None
    pledge_amount: Decimal | None = None
    client_equity: Decimal | None = None
    fx_pledge_occ: Decimal | None = None
    margin_occupied: Decimal | None = None
    delivery_margin: Decimal | None = None
    market_value_long: Decimal | None = None
    market_value_short: Decimal | None = None
    market_value_equity: Decimal | None = None
    fund_avail: Decimal | None = None
    risk_degree: Decimal | None = None
    margin_call: Decimal | None = None
    chg_in_fx_pledge: Decimal | None = None

    source_file: str = ""
    raw_payload: str | None = None


AccountDailySnapshot = AccountSummary
