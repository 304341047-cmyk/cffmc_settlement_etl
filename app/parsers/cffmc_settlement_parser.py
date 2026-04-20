from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional
import re
import warnings

import pandas as pd

from app.parsers.base import BaseParser
from app.models import (
    TradeExecution,
    PositionSnapshot,
    PositionDetail,
    AccountDailySnapshot,
    OptionExerciseDetail,
)

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class CFFMCSettlementParser(BaseParser):
    name = "CFFMCSettlementParser"

    REQUIRED_SHEETS = [
        "客户交易结算日报",
        "成交明细",
        "持仓明细",
    ]

    # =========================
    # 入口
    # =========================
    def can_parse(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in [".xlsx", ".xls"]:
            return False

        try:
            excel = pd.ExcelFile(file_path)
            return any(sheet in excel.sheet_names for sheet in self.REQUIRED_SHEETS)
        except Exception:
            return False

    def parse(self, file_path: Path):
        """
        统一解析入口：
        1. 账户日报
        2. 成交（期货 + 期权）
        3. 持仓明细（期货 + 期权）
        4. 持仓快照（由明细聚合）
        5. 行权明细
        6. 手续费校验
        """
        result = self.parse_result_template()

        accounts = self.parse_accounts(file_path)
        account_id = accounts[0].account_id if accounts else None

        futures_trades = self.parse_futures_trades(file_path, account_id=account_id)
        option_trades = self.parse_option_trades(file_path, account_id=account_id)
        trades = futures_trades + option_trades

        futures_position_details = self.parse_futures_position_details(file_path, account_id=account_id)
        option_position_details = self.parse_option_position_details_from_daily_sheet(file_path, account_id=account_id)
        position_details = futures_position_details + option_position_details
        positions = self.aggregate_position_details(position_details)

        exercise_details = self.parse_option_exercise_details_from_daily_sheet(
            file_path,
            account_id=account_id,
        )

        result["trades"] = trades
        result["position_details"] = position_details
        result["positions"] = positions
        result["exercise_details"] = exercise_details
        result["accounts"] = accounts
        result["validation"] = self.validate_result(trades, accounts)

        return result

    # =========================
    # 成交：期货
    # =========================
    def parse_futures_trades(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[TradeExecution]:
        df_raw = pd.read_excel(file_path, sheet_name="成交明细", header=None)
        header_row_index = self.find_trade_header_row(df_raw)
        if header_row_index is None:
            return []

        df = pd.read_excel(
            file_path,
            sheet_name="成交明细",
            header=header_row_index,
            dtype={"成交序号": str},
        )
        df = self.clean_dataframe_columns(df)

        trades: list[TradeExecution] = []
        for _, row in df.iterrows():
            trade = self.build_futures_trade_from_row(
                row=row,
                source_file=file_path.name,
                account_id=account_id,
            )
            if trade:
                trades.append(trade)

        return trades

    def find_trade_header_row(self, df_raw: pd.DataFrame) -> Optional[int]:
        keywords = ["合约", "买/卖", "成交价", "手数"]

        for i in range(len(df_raw)):
            row_values = [str(v).strip() for v in df_raw.iloc[i].tolist()]
            if sum(1 for k in keywords if k in row_values) >= 3:
                return i
        return None

    def build_futures_trade_from_row(
        self,
        row: pd.Series,
        source_file: str,
        account_id: str | None = None,
    ) -> Optional[TradeExecution]:
        instrument_code = self.get_str_value(row, "合约")
        if not instrument_code or self.is_summary_or_invalid_text(instrument_code):
            return None

        trade_date = self.parse_trade_date_from_filename(source_file)

        volume = self.get_int_value(row, "手数")
        price = self.get_decimal_value(row, "成交价")
        if volume is None or price is None:
            return None

        return TradeExecution(
            trade_date=trade_date,
            account_id=account_id,
            instrument_code=instrument_code,
            asset_type="futures",
            direction=self.map_direction(self.get_str_value(row, "买/卖")) or "unknown",
            open_close=self.map_open_close(self.get_str_value(row, "开/平")),
            volume=volume,
            price=price,
            turnover=self.get_decimal_value(row, "成交额"),
            commission=self.get_decimal_value(row, "手续费"),
            trade_time=self.get_datetime_value(row, "成交时间", trade_date),
            trade_no=self.get_trade_no_value(row, "成交序号"),
            source_file=source_file,
        )

    # =========================
    # 成交：期权
    # =========================
    def parse_option_trades(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[TradeExecution]:
        try:
            df_raw = pd.read_excel(file_path, sheet_name="期权成交明细", header=None)
        except Exception:
            return []

        header_row_index = self.find_option_trade_header_row(df_raw)
        if header_row_index is None:
            return []

        df = pd.read_excel(
            file_path,
            sheet_name="期权成交明细",
            header=header_row_index,
            dtype={"流水号": str},
        )
        df = self.clean_dataframe_columns(df)

        trades: list[TradeExecution] = []
        for _, row in df.iterrows():
            trade = self.build_option_trade_from_row(
                row=row,
                source_file=file_path.name,
                account_id=account_id,
            )
            if trade:
                trades.append(trade)

        return trades

    def find_option_trade_header_row(self, df_raw: pd.DataFrame) -> Optional[int]:
        keywords = ["品种合约", "流水号", "成交时间", "买/卖", "权利金单价", "成交量", "手续费"]

        for i in range(len(df_raw)):
            row_values = [str(v).strip() for v in df_raw.iloc[i].tolist()]
            if sum(1 for k in keywords if k in row_values) >= 5:
                return i
        return None

    def build_option_trade_from_row(
        self,
        row: pd.Series,
        source_file: str,
        account_id: str | None = None,
    ) -> Optional[TradeExecution]:
        instrument_code = self.get_str_value(row, "品种合约")
        if not instrument_code or self.is_summary_or_invalid_text(instrument_code):
            return None

        trade_date = self.parse_trade_date_from_filename(source_file)
        volume = self.get_int_value(row, "成交量")
        price = self.get_decimal_value(row, "权利金单价")
        if volume is None or price is None:
            return None

        trade_no_raw = self.get_trade_no_value(row, "流水号")
        trade_no = f"OPT_{trade_no_raw}" if trade_no_raw else None

        return TradeExecution(
            trade_date=trade_date,
            account_id=account_id,
            instrument_code=instrument_code,
            asset_type="option",
            direction=self.map_direction(self.get_str_value(row, "买/卖")) or "unknown",
            open_close=None,
            volume=volume,
            price=price,
            turnover=self.get_decimal_value(row, "权利金"),
            commission=self.get_decimal_value(row, "手续费"),
            trade_time=self.get_datetime_value(row, "成交时间", trade_date),
            trade_no=trade_no,
            source_file=source_file,
        )

    # =========================
    # 持仓明细：期货
    # =========================
    def parse_futures_position_details(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[PositionDetail]:
        df_raw = pd.read_excel(file_path, sheet_name="持仓明细", header=None)
        header_row_index = self.find_position_header_row(df_raw)
        if header_row_index is None:
            return []

        df = pd.read_excel(file_path, sheet_name="持仓明细", header=header_row_index)
        df = self.clean_dataframe_columns(df)

        details: list[PositionDetail] = []
        for idx, row in df.iterrows():
            detail_list = self.build_futures_position_details_from_row(
                row=row,
                source_file=file_path.name,
                account_id=account_id,
                raw_line_no=idx + header_row_index + 2,
            )
            details.extend(detail_list)

        return details

    def find_position_header_row(self, df_raw: pd.DataFrame) -> Optional[int]:
        keywords = ["合约", "买持仓", "卖持仓", "持仓盈亏", "今结算价"]

        for i in range(len(df_raw)):
            row_values = [str(v).strip() for v in df_raw.iloc[i].tolist()]
            if sum(1 for k in keywords if k in row_values) >= 3:
                return i
        return None

    def build_futures_position_details_from_row(
        self,
        row: pd.Series,
        source_file: str,
        account_id: str | None = None,
        raw_line_no: int | None = None,
    ) -> list[PositionDetail]:
        results: list[PositionDetail] = []

        instrument_code = self.get_str_value(row, "合约")
        if not instrument_code or self.is_summary_or_invalid_text(instrument_code):
            return results

        trade_date = self.parse_trade_date_from_filename(source_file)

        long_qty = self.get_int_value(row, "买持仓")
        short_qty = self.get_int_value(row, "卖持仓")

        if (not long_qty or long_qty <= 0) and (not short_qty or short_qty <= 0):
            return results

        long_price = self.get_decimal_value(row, "买入价")
        short_price = self.get_decimal_value(row, "卖出价")
        settlement_price = self.get_decimal_value(row, "今结算价")
        yesterday_settlement_price = self.get_decimal_value(row, "昨结算价")
        unrealized_pnl = self.get_decimal_value(row, "持仓盈亏")

        if long_qty and long_qty > 0:
            results.append(
                PositionDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    instrument_code=instrument_code,
                    asset_type="futures",
                    direction="long",
                    open_interest=long_qty,
                    avg_open_price=long_price,
                    settlement_price=settlement_price,
                    yesterday_settlement_price=yesterday_settlement_price,
                    unrealized_pnl=unrealized_pnl,
                    source_file=source_file,
                    source_section="持仓明细",
                    raw_line_no=raw_line_no,
                )
            )

        if short_qty and short_qty > 0:
            results.append(
                PositionDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    instrument_code=instrument_code,
                    asset_type="futures",
                    direction="short",
                    open_interest=short_qty,
                    avg_open_price=short_price,
                    settlement_price=settlement_price,
                    yesterday_settlement_price=yesterday_settlement_price,
                    unrealized_pnl=unrealized_pnl,
                    source_file=source_file,
                    source_section="持仓明细",
                    raw_line_no=raw_line_no,
                )
            )

        return results

    # =========================
    # 持仓明细：期权（嵌在日报）
    # =========================
    def parse_option_position_details_from_daily_sheet(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[PositionDetail]:
        df_raw = pd.read_excel(file_path, sheet_name="客户交易结算日报", header=None)

        header_row_index = self.find_option_position_header_row(df_raw)
        if header_row_index is None:
            return []

        section_df = self.extract_option_position_section(df_raw, header_row_index)
        if section_df.empty:
            return []

        section_df.columns = [str(v).strip() for v in df_raw.iloc[header_row_index].tolist()]
        section_df = section_df.dropna(how="all")

        details: list[PositionDetail] = []
        trade_date = self.parse_trade_date_from_filename(file_path.name)

        for idx, row in section_df.iterrows():
            detail_list = self.build_option_position_details_from_row(
                row=row,
                trade_date=trade_date,
                source_file=file_path.name,
                account_id=account_id,
                raw_line_no=idx + 1,
            )
            details.extend(detail_list)

        return details

    def find_option_position_header_row(self, df_raw: pd.DataFrame) -> Optional[int]:
        found_section = False

        for i in range(len(df_raw)):
            row_values = [str(v).strip() for v in df_raw.iloc[i].tolist()]
            normalized = [v.replace(" ", "") for v in row_values]

            if any("期权持仓汇总" in v for v in normalized):
                found_section = True
                continue

            if not found_section:
                continue

            required = ["品种合约", "标的合约", "期权类型", "执行价", "买持仓", "卖持仓", "今结算价"]
            if sum(1 for k in required if k in row_values) >= 5:
                return i

        return None

    def extract_option_position_section(
        self,
        df_raw: pd.DataFrame,
        header_row_index: int,
    ) -> pd.DataFrame:
        """
        只截取期权持仓区块，不把后面的行权明细等区块吃进来。
        """
        stop_keywords = [
            "行权明细",
            "履约明细",
            "交割明细",
            "期权类型汇总",
            "期权品种汇总",
            "品种汇总",
            "证券成交明细",
            "资金明细",
            "交易所",
        ]

        rows = []
        empty_streak = 0

        for i in range(header_row_index + 1, len(df_raw)):
            row = df_raw.iloc[i]
            row_values = [str(v).strip() if not pd.isna(v) else "" for v in row.tolist()]
            joined = "".join(row_values).replace(" ", "")

            if not any(row_values):
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            else:
                empty_streak = 0

            if any(keyword in joined for keyword in stop_keywords):
                break

            rows.append(row)

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def build_option_position_details_from_row(
        self,
        row: pd.Series,
        trade_date,
        source_file: str,
        account_id: str | None = None,
        raw_line_no: int | None = None,
    ) -> list[PositionDetail]:
        results: list[PositionDetail] = []

        instrument_code = self.get_str_value(row, "品种合约")
        underlying = self.get_str_value(row, "标的合约")
        option_type_text = self.get_str_value(row, "期权类型")
        strike_price = self.get_decimal_value(row, "执行价")

        if not self.is_valid_option_position_row(
            instrument_code=instrument_code,
            option_type_text=option_type_text,
            strike_price=strike_price,
            row=row,
        ):
            return results

        long_qty = self.get_int_value(row, "买持仓")
        short_qty = self.get_int_value(row, "卖持仓")

        long_price = self.get_decimal_value(row, "买均价")
        short_price = self.get_decimal_value(row, "卖均价")
        settlement_price = self.get_decimal_value(row, "今结算价")
        yesterday_settlement_price = self.get_decimal_value(row, "昨结算价")
        margin_occupied = self.get_decimal_value(row, "交易保证金")

        if long_qty and long_qty > 0:
            results.append(
                PositionDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    instrument_code=instrument_code,
                    instrument_name=underlying,
                    asset_type="option",
                    direction="long",
                    open_interest=long_qty,
                    avg_open_price=long_price,
                    settlement_price=settlement_price,
                    yesterday_settlement_price=yesterday_settlement_price,
                    margin_occupied=Decimal("0"),
                    source_file=source_file,
                    source_section="期权持仓汇总",
                    raw_line_no=raw_line_no,
                )
            )

        if short_qty and short_qty > 0:
            results.append(
                PositionDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    instrument_code=instrument_code,
                    instrument_name=underlying,
                    asset_type="option",
                    direction="short",
                    open_interest=short_qty,
                    avg_open_price=short_price,
                    settlement_price=settlement_price,
                    yesterday_settlement_price=yesterday_settlement_price,
                    margin_occupied=margin_occupied,
                    source_file=source_file,
                    source_section="期权持仓汇总",
                    raw_line_no=raw_line_no,
                )
            )

        return results

    def is_valid_option_position_row(
        self,
        instrument_code: Optional[str],
        option_type_text: Optional[str],
        strike_price: Optional[Decimal],
        row: pd.Series,
    ) -> bool:
        if not instrument_code:
            return False

        invalid_texts = [
            "大连商品交易所",
            "郑州商品交易所",
            "上海期货交易所",
            "中国金融期货交易所",
            "广州期货交易所",
            "合计",
            "小计",
            "总计",
            "行权明细",
            "履约明细",
            "交割明细",
        ]
        if any(x in instrument_code for x in invalid_texts):
            return False

        if option_type_text not in ("看涨期权", "看跌期权"):
            return False

        if strike_price is None:
            return False

        long_qty = self.get_int_value(row, "买持仓")
        short_qty = self.get_int_value(row, "卖持仓")
        return (long_qty and long_qty > 0) or (short_qty and short_qty > 0)

    # =========================
    # 行权明细（嵌在日报）
    # =========================
    def parse_option_exercise_details_from_daily_sheet(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[OptionExerciseDetail]:
        """
        按当前结算单格式解析“期权行权明细”区块。
        """
        df_raw = pd.read_excel(file_path, sheet_name="客户交易结算日报", header=None)

        title_row_index = None
        header_row_index = None

        for i in range(len(df_raw)):
            row_values = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[i].tolist()]
            joined = "".join(row_values).replace(" ", "")

            if "期权行权明细" in joined:
                title_row_index = i
                break

        if title_row_index is None:
            return []

        for i in range(title_row_index + 1, min(title_row_index + 5, len(df_raw))):
            row_values = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[i].tolist()]
            required = ["交易所", "品种合约", "标的合约", "执行价", "行权日期", "买/卖", "成交量", "手续费"]

            if sum(1 for k in required if k in row_values) >= 5:
                header_row_index = i
                break

        if header_row_index is None:
            return []

        sub_df = df_raw.iloc[header_row_index + 1:].copy()
        sub_df.columns = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[header_row_index].tolist()]
        sub_df = sub_df.dropna(how="all")

        details: list[OptionExerciseDetail] = []
        trade_date = self.parse_trade_date_from_filename(file_path.name)

        for idx, row in sub_df.iterrows():
            exchange = self.get_str_value(row, "交易所")
            instrument_code = self.get_str_value(row, "品种合约")

            if exchange == "合计" or instrument_code == "合计":
                break

            if not exchange and not instrument_code:
                continue

            quantity = self.get_int_value(row, "成交量")
            if not exchange or not instrument_code or quantity is None:
                continue

            details.append(
                OptionExerciseDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    exchange=exchange,
                    instrument_code=instrument_code,
                    underlying=self.get_str_value(row, "标的合约"),
                    direction=self.map_direction(self.get_str_value(row, "买/卖")),
                    exercise_type="行权",
                    quantity=quantity,
                    price=self.get_decimal_value(row, "执行价"),
                    amount=self.get_decimal_value(row, "行权盈亏"),
                    commission=self.get_decimal_value(row, "手续费"),
                    source_file=file_path.name,
                    source_section="期权行权明细",
                    raw_line_no=idx + 1,
                )
            )

        return details

    # =========================
    # 持仓快照：由明细聚合
    # =========================
    def aggregate_position_details(
        self,
        position_details: list[PositionDetail],
    ) -> list[PositionSnapshot]:
        grouped = {}

        for pos in position_details:
            key = (
                pos.account_id,
                pos.trade_date,
                pos.instrument_code,
                pos.direction,
            )

            if key not in grouped:
                grouped[key] = {
                    "trade_date": pos.trade_date,
                    "account_id": pos.account_id,
                    "instrument_code": pos.instrument_code,
                    "instrument_name": pos.instrument_name,
                    "asset_type": pos.asset_type,
                    "direction": pos.direction,
                    "open_interest": 0,
                    "avg_open_price_amount": Decimal("0"),
                    "settlement_price": pos.settlement_price,
                    "unrealized_pnl": Decimal("0"),
                    "margin_occupied": Decimal("0"),
                    "source_file": pos.source_file,
                }

            item = grouped[key]
            qty = pos.open_interest or 0
            avg_price = pos.avg_open_price or Decimal("0")

            item["open_interest"] += qty
            item["avg_open_price_amount"] += avg_price * qty

            if pos.unrealized_pnl:
                item["unrealized_pnl"] += pos.unrealized_pnl

            if pos.margin_occupied:
                item["margin_occupied"] += pos.margin_occupied

            if pos.settlement_price is not None:
                item["settlement_price"] = pos.settlement_price

        results: list[PositionSnapshot] = []

        for item in grouped.values():
            qty = item["open_interest"]
            avg_open_price = None
            if qty > 0:
                avg_open_price = item["avg_open_price_amount"] / Decimal(str(qty))

            results.append(
                PositionSnapshot(
                    trade_date=item["trade_date"],
                    account_id=item["account_id"],
                    instrument_code=item["instrument_code"],
                    instrument_name=item["instrument_name"],
                    asset_type=item["asset_type"],
                    direction=item["direction"],
                    open_interest=item["open_interest"],
                    avg_open_price=avg_open_price,
                    settlement_price=item["settlement_price"],
                    unrealized_pnl=item["unrealized_pnl"] or None,
                    margin_occupied=item["margin_occupied"] or None,
                    source_file=item["source_file"],
                )
            )

        return results

    # =========================
    # 账户日报
    # =========================
    def parse_accounts(self, file_path: Path) -> list[AccountDailySnapshot]:
        df = pd.read_excel(file_path, sheet_name="客户交易结算日报", header=None)

        data_map = self.extract_key_value_pairs(df)
        other_fund_map = self.extract_other_fund_details(df)

        trade_date = self.parse_trade_date_from_filename(file_path.name)

        begin_balance = self.get_decimal_from_map(data_map, "上日结存")
        end_balance = self.get_decimal_from_map(data_map, "当日结存")
        deposit_withdrawal_total = self.get_decimal_from_map(data_map, "当日存取合计")

        deposit = None
        withdrawal = None
        if deposit_withdrawal_total is not None:
            if deposit_withdrawal_total >= 0:
                deposit = deposit_withdrawal_total
                withdrawal = Decimal("0")
            else:
                deposit = Decimal("0")
                withdrawal = abs(deposit_withdrawal_total)

        total_commission = self.get_decimal_from_map(data_map, "当日手续费")
        futures_commission = other_fund_map.get("交易手续费")
        exercise_commission = other_fund_map.get("行权手续费")

        if futures_commission is not None:
            futures_commission = abs(futures_commission)
        if exercise_commission is not None:
            exercise_commission = abs(exercise_commission)

        option_commission = None
        if total_commission is not None:
            futures_val = futures_commission or Decimal("0")
            exercise_val = exercise_commission or Decimal("0")
            option_commission = total_commission - futures_val - exercise_val

        account = AccountDailySnapshot(
            trade_date=trade_date,
            account_id=self.get_str_from_map(data_map, "客户期货期权内部资金账户"),
            broker=self.get_str_from_map(data_map, "期货公司名称"),

            # 兼容旧字段
            begin_client_equity=begin_balance,
            end_client_equity=end_balance,

            # 原始日报字段
            begin_balance=begin_balance,
            deposit=deposit,
            withdrawal=withdrawal,
            premium=self.get_decimal_from_map(data_map, "当日总权利金"),
            non_fx_pledge=self.get_decimal_from_map(data_map, "非货币充抵金额"),
            fx_pledge=self.get_decimal_from_map(data_map, "货币充抵金额"),
            frozen_cash=self.get_decimal_from_map(data_map, "冻结资金"),
            margin_call=self.get_decimal_from_map(data_map, "追加保证金"),

            # 资金风险字段
            available_fund=self.get_decimal_from_map(data_map, "可用资金"),
            margin_occupied=self.get_decimal_from_map(data_map, "保证金占用"),
            realized_pnl=self.get_decimal_from_map(data_map, "当日盈亏"),
            commission=self.get_value_from_sheet(df, "当日手续费"),
            option_commission=option_commission,
            exercise_commission=exercise_commission,
            risk_degree=self.get_percent_from_map(data_map, "风险度"),
            source_file=file_path.name,
        )

        return [account]

    def extract_key_value_pairs(self, df: pd.DataFrame) -> dict:
        result = {}

        for i in range(len(df)):
            for j in range(len(df.columns)):
                key = df.iat[i, j]

                if pd.isna(key):
                    continue

                key_str = str(key).strip()
                if not key_str:
                    continue

                value = None
                for k in range(j + 1, len(df.columns)):
                    v = df.iat[i, k]
                    if not pd.isna(v):
                        value = v
                        break

                if value is not None:
                    result[key_str] = value

        return result

    def extract_other_fund_details(self, df: pd.DataFrame) -> dict:
        """
        从“其它资金明细”中提取交易手续费、行权手续费。
        """
        result = {
            "交易手续费": Decimal("0"),
            "行权手续费": Decimal("0"),
        }

        start_row = None
        for i in range(len(df)):
            row = [str(v).strip() if v is not None else "" for v in df.iloc[i].tolist()]
            normalized = [cell.replace(" ", "") for cell in row]
            if any("其它资金明细" in cell for cell in normalized):
                start_row = i
                break

        if start_row is None:
            return result

        header_row = start_row + 1
        sub_df = df.iloc[header_row + 1: min(header_row + 10, len(df))].copy()
        sub_df.columns = [str(v).strip() for v in df.iloc[header_row].tolist()]
        sub_df = sub_df.dropna(how="all")

        if "类型" not in sub_df.columns or "金额" not in sub_df.columns:
            return result

        for _, row in sub_df.iterrows():
            date_val = str(row["发生日期"]).strip() if "发生日期" in sub_df.columns and row["发生日期"] is not None else ""
            fee_type = str(row["类型"]).strip() if row["类型"] is not None else ""
            amount_val = row["金额"]

            if not fee_type or pd.isna(amount_val):
                continue

            if date_val == "合计":
                continue

            if fee_type in result:
                try:
                    result[fee_type] += Decimal(str(amount_val).replace(",", "").strip())
                except Exception:
                    continue

        return result

    # =========================
    # 校验
    # =========================
    def validate_result(
        self,
        trades: list[TradeExecution],
        accounts: list[AccountDailySnapshot],
    ) -> dict:
        futures_commission = Decimal("0")
        option_trade_commission = Decimal("0")

        for trade in trades:
            if trade.commission is None:
                continue

            if trade.asset_type == "option":
                option_trade_commission += abs(trade.commission)
            else:
                futures_commission += abs(trade.commission)

        account_total = None
        exercise_commission = Decimal("0")

        if accounts:
            acc = accounts[0]
            account_total = acc.commission
            exercise_commission = acc.exercise_commission or Decimal("0")

        total_calc = futures_commission + option_trade_commission + exercise_commission

        diff = None
        is_match = None
        if account_total is not None:
            diff = total_calc - account_total
            is_match = abs(diff) <= Decimal("0.01")

        return {
            "commission_check": {
                "futures": futures_commission,
                "option": option_trade_commission,
                "exercise": exercise_commission,
                "total_calc": total_calc,
                "account": account_total,
                "diff": diff,
                "is_match": is_match,
            }
        }

    # =========================
    # 通用工具
    # =========================
    def clean_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna(how="all")
        df.columns = [str(col).strip() for col in df.columns]
        return df

    def get_str_value(self, row: pd.Series, column_name: str) -> Optional[str]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        if isinstance(value, (int, float)):
            if float(value).is_integer():
                return str(int(value))
            return str(value).strip()

        value = str(value).strip()
        return value if value else None

    def get_decimal_value(self, row: pd.Series, column_name: str) -> Optional[Decimal]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        try:
            text = str(value).replace(",", "").strip()
            if text == "":
                return None
            return Decimal(text)
        except Exception:
            return None

    def get_int_value(self, row: pd.Series, column_name: str) -> Optional[int]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        try:
            return int(float(value))
        except Exception:
            return None

    def get_datetime_value(
        self,
        row: pd.Series,
        column_name: str,
        trade_date,
    ) -> Optional[datetime]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        text = str(value).strip()
        if not text:
            return None

        try:
            time_obj = datetime.strptime(text, "%H:%M:%S").time()
            return datetime.combine(trade_date, time_obj)
        except Exception:
            pass

        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return None

    def map_direction(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        mapping = {
            "买": "buy",
            "卖": "sell",
        }
        return mapping.get(value.strip(), value)

    def map_open_close(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        mapping = {
            "开": "open",
            "平": "close",
            "平今": "close_today",
            "平昨": "close_yesterday",
        }
        return mapping.get(value.strip(), value)

    def parse_trade_date_from_filename(self, filename: str):
        """
        从文件名中提取交易日，例如：
        016081183126_2026-04-13.xlsx -> 2026-04-13
        """
        match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
        if not match:
            raise ValueError(f"无法从文件名提取交易日期: {filename}")

        return datetime.strptime(match.group(1), "%Y-%m-%d").date()

    # =========================
    # 账户日报
    # =========================
    def parse_accounts(self, file_path: Path) -> list[AccountDailySnapshot]:
        """
        解析“客户交易结算日报”中的账户资金快照。

        说明：
        1. begin_client_equity 继续保留，兼容旧逻辑
        2. begin_balance / premium / pledge / frozen_cash / margin_call 等字段补齐
        3. 当日存取合计拆为 deposit / withdrawal
        """
        sheet_name = "客户交易结算日报"
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

        data_map = self.extract_key_value_pairs(df)
        other_fund_map = self.extract_other_fund_details(df)

        trade_date = self.parse_trade_date_from_filename(file_path.name)

        # ===== 原始日报字段 =====
        begin_balance = self.get_decimal_from_map(data_map, "上日结存")
        end_balance = self.get_decimal_from_map(data_map, "当日结存")
        net_deposit = self.get_decimal_from_map(data_map, "当日存取合计")
        premium = self.get_decimal_from_map(data_map, "当日总权利金")
        non_fx_pledge = self.get_decimal_from_map(data_map, "非货币充抵金额")
        fx_pledge = self.get_decimal_from_map(data_map, "货币充抵金额")
        frozen_cash = self.get_decimal_from_map(data_map, "冻结资金")
        margin_call = self.get_decimal_from_map(data_map, "追加保证金")

        deposit, withdrawal = self.split_net_deposit_withdrawal(net_deposit)

        # ===== 手续费相关 =====
        total_commission = self.get_decimal_from_map(data_map, "当日手续费")
        futures_commission = other_fund_map.get("交易手续费")
        exercise_commission = other_fund_map.get("行权手续费")

        if futures_commission is not None:
            futures_commission = abs(futures_commission)

        if exercise_commission is not None:
            exercise_commission = abs(exercise_commission)

        option_commission = None
        if total_commission is not None:
            futures_val = futures_commission or Decimal("0")
            exercise_val = exercise_commission or Decimal("0")
            option_commission = total_commission - futures_val - exercise_val

        account = AccountDailySnapshot(
            trade_date=trade_date,
            account_id=self.get_str_from_map(data_map, "客户期货期权内部资金账户"),
            broker=self.get_str_from_map(data_map, "期货公司名称"),

            # 兼容旧字段
            begin_client_equity=begin_balance,
            end_client_equity=end_balance,

            # 原始日报字段
            begin_balance=begin_balance,
            deposit=deposit,
            withdrawal=withdrawal,
            premium=premium,
            non_fx_pledge=non_fx_pledge,
            fx_pledge=fx_pledge,
            frozen_cash=frozen_cash,
            margin_call=margin_call,

            # 资金 / 风险
            available_fund=self.get_decimal_from_map(data_map, "可用资金"),
            margin_occupied=self.get_decimal_from_map(data_map, "保证金占用"),
            realized_pnl=self.get_decimal_from_map(data_map, "当日盈亏"),
            commission=total_commission,
            option_commission=option_commission,
            exercise_commission=exercise_commission,
            risk_degree=self.get_percent_from_map(data_map, "风险度"),
            source_file=file_path.name,
        )

        return [account]

    def split_net_deposit_withdrawal(
        self,
        net_amount: Optional[Decimal],
    ) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """
        将“当日存取合计”拆分成：
        - deposit：入金
        - withdrawal：出金

        约定：
        - 正数 -> 入金
        - 负数 -> 出金（取绝对值）
        - 0 / None -> 两者都为 0 或 None
        """
        if net_amount is None:
            return None, None

        if net_amount > 0:
            return net_amount, Decimal("0")

        if net_amount < 0:
            return Decimal("0"), abs(net_amount)

        return Decimal("0"), Decimal("0")

    def extract_key_value_pairs(self, df: pd.DataFrame) -> dict:
        """
        从日报中提取“键值对”型字段。
        做法：
        - 扫描每一个非空单元格作为 key
        - 向右找第一个非空值作为 value
        """
        result = {}

        for i in range(len(df)):
            for j in range(len(df.columns)):
                key = df.iat[i, j]

                if pd.isna(key):
                    continue

                key_str = str(key).strip()
                if not key_str:
                    continue

                value = None
                for k in range(j + 1, len(df.columns)):
                    v = df.iat[i, k]
                    if not pd.isna(v):
                        value = v
                        break

                if value is not None:
                    result[key_str] = value

        return result

    def extract_other_fund_details(self, df: pd.DataFrame) -> dict:
        """
        从“其它资金明细”区块中提取手续费相关项。

        当前只关心：
        - 交易手续费
        - 行权手续费
        """
        result = {
            "交易手续费": Decimal("0"),
            "行权手续费": Decimal("0"),
        }

        start_row = None

        for i in range(len(df)):
            row = [str(v).strip() if v is not None else "" for v in df.iloc[i].tolist()]
            normalized = [cell.replace(" ", "") for cell in row]

            if any("其它资金明细" in cell for cell in normalized):
                start_row = i
                break

        if start_row is None:
            return result

        header_row = start_row + 1
        sub_df = df.iloc[header_row + 1: min(header_row + 12, len(df))].copy()
        sub_df.columns = [str(v).strip() for v in df.iloc[header_row].tolist()]
        sub_df = sub_df.dropna(how="all")

        if "类型" not in sub_df.columns or "金额" not in sub_df.columns:
            return result

        for _, row in sub_df.iterrows():
            date_val = (
                str(row["发生日期"]).strip()
                if "发生日期" in sub_df.columns and row["发生日期"] is not None
                else ""
            )
            fee_type = str(row["类型"]).strip() if row["类型"] is not None else ""
            amount_val = row["金额"]

            if not fee_type or pd.isna(amount_val):
                continue

            if date_val == "合计":
                continue

            if fee_type in result:
                try:
                    result[fee_type] += Decimal(str(amount_val).replace(",", "").strip())
                except Exception:
                    continue

        return result

    # =========================
    # 行权明细（嵌在日报）
    # =========================
    def parse_option_exercise_details_from_daily_sheet(
        self,
        file_path: Path,
        account_id: str | None = None,
    ) -> list[OptionExerciseDetail]:
        """
        从“客户交易结算日报”中解析“期权行权明细”区块。

        当前按已验证过的格式处理：
        标题行 -> 表头行 -> 数据行 -> 合计结束
        """
        sheet_name = "客户交易结算日报"
        df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

        title_row_index = None
        header_row_index = None

        # 1. 找标题
        for i in range(len(df_raw)):
            row_values = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[i].tolist()]
            joined = "".join(row_values).replace(" ", "")

            if "期权行权明细" in joined:
                title_row_index = i
                break

        if title_row_index is None:
            return []

        # 2. 找表头
        for i in range(title_row_index + 1, min(title_row_index + 5, len(df_raw))):
            row_values = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[i].tolist()]
            required = ["交易所", "品种合约", "标的合约", "执行价", "行权日期", "买/卖", "成交量", "手续费"]
            hit_count = sum(1 for k in required if k in row_values)

            if hit_count >= 5:
                header_row_index = i
                break

        if header_row_index is None:
            return []

        # 3. 数据区
        sub_df = df_raw.iloc[header_row_index + 1:].copy()
        sub_df.columns = [str(v).strip() if not pd.isna(v) else "" for v in df_raw.iloc[header_row_index].tolist()]
        sub_df = sub_df.dropna(how="all")

        details: list[OptionExerciseDetail] = []
        trade_date = self.parse_trade_date_from_filename(file_path.name)
        source_file = file_path.name

        for idx, row in sub_df.iterrows():
            exchange = self.get_str_value(row, "交易所")
            instrument_code = self.get_str_value(row, "品种合约")

            # 遇到合计行，停止
            if exchange == "合计" or instrument_code == "合计":
                break

            # 空行跳过
            if not exchange and not instrument_code:
                continue

            underlying = self.get_str_value(row, "标的合约")
            direction_raw = self.get_str_value(row, "买/卖")
            quantity = self.get_int_value(row, "成交量")
            commission = self.get_decimal_value(row, "手续费")
            amount = self.get_decimal_value(row, "行权盈亏")
            price = self.get_decimal_value(row, "执行价")

            if not exchange or not instrument_code or quantity is None:
                continue

            details.append(
                OptionExerciseDetail(
                    trade_date=trade_date,
                    account_id=account_id,
                    exchange=exchange,
                    instrument_code=instrument_code,
                    underlying=underlying,
                    direction=self.map_direction(direction_raw) if direction_raw else direction_raw,
                    exercise_type="行权",
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    commission=commission,
                    source_file=source_file,
                    source_section="期权行权明细",
                    raw_line_no=idx + 1,
                )
            )

        return details

    # =========================
    # 校验
    # =========================
    def validate_result(
        self,
        trades: list[TradeExecution],
        accounts: list[AccountDailySnapshot],
    ) -> dict:
        """
        当前只保留“手续费总额校验”，不在 ETL 中做更复杂勾稽。
        """
        result = {}

        futures_commission = Decimal("0")
        option_trade_commission = Decimal("0")

        for trade in trades:
            if trade.commission is None:
                continue

            if trade.asset_type == "option":
                option_trade_commission += abs(trade.commission)
            else:
                futures_commission += abs(trade.commission)

        account_total = None
        exercise_commission = Decimal("0")

        if accounts:
            acc = accounts[0]
            account_total = acc.commission
            exercise_commission = acc.exercise_commission or Decimal("0")

        total_calc = futures_commission + option_trade_commission + exercise_commission

        diff = None
        is_match = None
        if account_total is not None:
            diff = total_calc - account_total
            is_match = abs(diff) <= Decimal("0.01")

        result["commission_check"] = {
            "futures": futures_commission,
            "option": option_trade_commission,
            "exercise": exercise_commission,
            "total_calc": total_calc,
            "account": account_total,
            "diff": diff,
            "is_match": is_match,
        }

        return result

    # =========================
    # 通用工具
    # =========================
    def get_str_value(self, row: pd.Series, column_name: str) -> Optional[str]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        if isinstance(value, (int, float)):
            if float(value).is_integer():
                return str(int(value))
            return str(value).strip()

        value = str(value).strip()
        return value if value else None

    def get_decimal_value(self, row: pd.Series, column_name: str) -> Optional[Decimal]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        try:
            value_str = str(value).replace(",", "").strip()
            if value_str == "":
                return None
            return Decimal(value_str)
        except Exception:
            return None

    def get_int_value(self, row: pd.Series, column_name: str) -> Optional[int]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        try:
            return int(float(value))
        except Exception:
            return None

    def get_datetime_value(
        self,
        row: pd.Series,
        column_name: str,
        trade_date,
    ) -> Optional[datetime]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        text = str(value).strip()
        if not text:
            return None

        try:
            time_obj = datetime.strptime(text, "%H:%M:%S").time()
            return datetime.combine(trade_date, time_obj)
        except Exception:
            pass

        try:
            return pd.to_datetime(value).to_pydatetime()
        except Exception:
            return None

    def map_direction(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        mapping = {
            "买": "buy",
            "卖": "sell",
        }
        return mapping.get(value.strip(), value)

    def map_open_close(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        mapping = {
            "开": "open",
            "平": "close",
            "平今": "close_today",
            "平昨": "close_yesterday",
        }
        return mapping.get(value.strip(), value)

    def get_decimal_from_map(self, data_map: dict, key: str):
        """
        用“规范化字符串包含匹配”取日报字段，兼容冒号、空格等格式差异。
        """
        key_norm = self.normalize_text(key)

        for k, v in data_map.items():
            k_norm = self.normalize_text(k)

            if key_norm in k_norm:
                try:
                    return Decimal(str(v).replace(",", "").strip())
                except Exception:
                    return None

        return None

    def get_percent_from_map(self, data_map: dict, key: str) -> Optional[Decimal]:
        value = data_map.get(key)
        if value is None:
            return None

        try:
            text = str(value).replace("%", "").strip()
            return Decimal(text) / Decimal("100")
        except Exception:
            return None

    def get_str_from_map(self, data_map: dict, key: str) -> Optional[str]:
        value = data_map.get(key)
        if value is None:
            return None
        return str(value).strip()

    def get_trade_no_value(self, row: pd.Series, column_name: str) -> Optional[str]:
        if column_name not in row.index:
            return None

        value = row[column_name]
        if pd.isna(value):
            return None

        text = str(value).strip()
        if not text:
            return None

        if text.endswith(".0"):
            text = text[:-2]

        return text

    def is_summary_or_invalid_text(self, text: str) -> bool:
        if not text:
            return True

        text = str(text).strip()

        invalid_keywords = [
            "合计",
            "小计",
            "总计",
            "成交明细",
            "持仓明细",
            "基本资料",
        ]

        return any(keyword in text for keyword in invalid_keywords)

    def normalize_text(self, s: str) -> str:
        return (
            str(s)
            .replace(" ", "")
            .replace("：", "")
            .replace(":", "")
            .strip()
        )