from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime, date


class TradeExecution(BaseModel):
    trade_date: date = Field(..., description="交易日期")
    account_id: Optional[str] = Field(None, description="账户编号")
    instrument_code: str = Field(..., description="合约或证券代码")
    instrument_name: Optional[str] = Field(None, description="合约或证券名称")
    asset_type: Optional[str] = Field(None, description="资产类型：futures/stock/option")
    market: Optional[str] = Field(None, description="市场，如 SHFE / CFFEX / SSE / SZSE")

    direction: str = Field(..., description="买卖方向：buy/sell")
    open_close: Optional[str] = Field(None, description="开平方向：open/close/close_today")
    volume: int = Field(..., description="成交数量")
    price: Decimal = Field(..., description="成交价格")
    turnover: Optional[Decimal] = Field(None, description="成交金额")
    commission: Optional[Decimal] = Field(None, description="手续费")

    trade_time: Optional[datetime] = Field(None, description="成交时间")
    trade_no: Optional[str] = Field(None, description="成交编号")

    source_file: Optional[str] = Field(None, description="来源文件名")
    sheet_name: Optional[str] = None
    raw_line_no: Optional[int] = None
    row_hash: Optional[str] = None
