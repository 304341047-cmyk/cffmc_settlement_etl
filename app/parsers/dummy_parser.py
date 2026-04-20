from pathlib import Path
from datetime import date
from decimal import Decimal

from app.parsers.base import BaseParser
from app.models import TradeExecution, PositionSnapshot, AccountDailySnapshot


class DummyParser(BaseParser):
    name = "DummyParser"

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in [".xlsx", ".xls"]

    def parse(self, file_path: Path):
        result = self.parse_result_template()

        # 1. 模拟成交记录
        trade = TradeExecution(
            trade_date=date.today(),
            instrument_code="TEST001",
            instrument_name="测试合约",
            asset_type="futures",
            market="CFFEX",
            direction="buy",
            open_close="open",
            volume=1,
            price=Decimal("100.0"),
            turnover=Decimal("100.0"),
            commission=Decimal("1.2"),
            trade_no="T0001",
            source_file=file_path.name,
        )

        # 2. 模拟持仓快照
        position = PositionSnapshot(
            trade_date=date.today(),
            instrument_code="TEST001",
            instrument_name="测试合约",
            asset_type="futures",
            direction="long",
            open_interest=1,
            yesterday_open_interest=0,
            avg_open_price=Decimal("100.0"),
            settlement_price=Decimal("101.5"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("1.5"),
            option_pnl=Decimal("0"),
            margin_occupied=Decimal("12.0"),
            source_file=file_path.name,
        )

        # 3. 模拟账户日快照
        account = AccountDailySnapshot(
            trade_date=date.today(),
            account_id="DEMO001",
            broker="DummyBroker",
            begin_client_equity=Decimal("100000"),
            end_client_equity=Decimal("100120.3"),
            available_fund=Decimal("85000"),
            margin_occupied=Decimal("12000"),
            deposit=Decimal("0"),
            withdrawal=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("120.3"),
            commission=Decimal("1.2"),
            risk_degree=Decimal("0.12"),
            source_file=file_path.name,
        )

        result["trades"].append(trade)
        result["positions"].append(position)
        result["accounts"].append(account)

        return result