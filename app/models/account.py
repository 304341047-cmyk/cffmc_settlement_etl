from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class AccountDailySnapshot(BaseModel):
    """
    账户日报快照（来自“客户交易结算日报”）

    说明：
    1. 为了兼容现有逻辑，保留 begin_client_equity / end_client_equity
    2. 同时补录更贴近原始日报字段的值，便于后续下游分析项目直接使用
    """

    trade_date: date
    account_id: str | None = None
    broker: str | None = None

    # ===== 兼容旧字段 =====
    begin_client_equity: Decimal | None = None   # 兼容旧逻辑，等于 begin_balance
    end_client_equity: Decimal | None = None     # 对应当日结存

    # ===== 原始日报字段 =====
    begin_balance: Decimal | None = None         # 上日结存
    deposit: Decimal | None = None               # 入金（由“当日存取合计”拆分）
    withdrawal: Decimal | None = None            # 出金（由“当日存取合计”拆分）
    premium: Decimal | None = None               # 当日总权利金
    non_fx_pledge: Decimal | None = None         # 非货币充抵金额
    fx_pledge: Decimal | None = None             # 货币充抵金额
    frozen_cash: Decimal | None = None           # 冻结资金
    margin_call: Decimal | None = None           # 追加保证金

    # ===== 资金/风险相关 =====
    available_fund: Decimal | None = None
    margin_occupied: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    commission: Decimal | None = None
    option_commission: Decimal | None = None
    exercise_commission: Decimal | None = None
    risk_degree: Decimal | None = None

    source_file: str | None = None