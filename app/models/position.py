from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import date


class PositionSnapshot(BaseModel):
    trade_date: date = Field(..., description="交易日期")
    account_id: Optional[str] = Field(None, description="账户编号")
    instrument_code: str = Field(..., description="合约或证券代码")
    instrument_name: Optional[str] = Field(None, description="合约或证券名称")
    asset_type: Optional[str] = Field(None, description="资产类型")

    direction: Optional[str] = Field(None, description="持仓方向：long/short")
    open_interest: int = Field(..., description="持仓数量")
    yesterday_open_interest: Optional[int] = Field(None, description="昨仓数量")

    avg_open_price: Optional[Decimal] = Field(None, description="开仓均价")
    settlement_price: Optional[Decimal] = Field(None, description="结算价")
    realized_pnl: Optional[Decimal] = Field(None, description="期货平仓盈亏")
    unrealized_pnl: Optional[Decimal] = Field(None, description="持仓盯市盈亏")
    option_pnl: Optional[Decimal] = Field(None, description="期权浮动盈亏")
    margin_occupied: Optional[Decimal] = Field(None, description="占用保证金")

    source_file: Optional[str] = Field(None, description="来源文件名")