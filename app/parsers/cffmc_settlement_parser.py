from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import warnings

import pandas as pd

from app.models import (
    AccountSummary,
    DepositWithdrawal,
    ExerciseStatement,
    PositionClosed,
    Positions,
    PositionsDetail,
    TransactionRecord,
    ValidationResult,
)
from app.parsers.base import BaseParser

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class CFFMCSettlementParser(BaseParser):
    name = "CFFMCSettlementParser"

    REQUIRED_SHEETS = ["客户交易结算日报", "成交明细", "持仓明细"]

    def can_parse(self, file_path: Path) -> bool:
        if file_path.suffix.lower() not in {".xlsx", ".xls"}:
            return False
        try:
            excel = pd.ExcelFile(file_path)
            return any(sheet in excel.sheet_names for sheet in self.REQUIRED_SHEETS)
        except Exception:
            return False

    def parse(self, file_path: Path) -> dict[str, Any]:
        result = self.parse_result_template()

        account_rows = self.parse_account_summary(file_path)
        account_id = account_rows[0].account_id if account_rows else None
        trade_date = self.trade_date_from_file(file_path.name)

        transaction_rows = []
        transaction_rows.extend(self.parse_futures_transactions(file_path, account_id))
        transaction_rows.extend(self.parse_option_transactions(file_path, account_id))

        position_detail_rows = []
        position_detail_rows.extend(self.parse_futures_positions_detail(file_path, account_id))
        position_detail_rows.extend(self.parse_option_positions_detail(file_path, account_id))

        result["account_summary"] = account_rows
        result["deposit_withdrawal"] = self.parse_deposit_withdrawal(file_path, account_id)
        result["transaction_record"] = transaction_rows
        result["exercise_statement"] = self.parse_exercise_statement(file_path, account_id)
        result["position_closed"] = self.parse_position_closed(file_path, account_id)
        result["positions_detail"] = position_detail_rows
        result["positions"] = self.aggregate_positions(position_detail_rows, trade_date, file_path.name)
        result["validation_result"] = self.validate_commission(result, trade_date, account_id, file_path.name)
        return result

    # ------------------------------------------------------------------
    # Account and cash sections
    # ------------------------------------------------------------------
    def parse_account_summary(self, file_path: Path) -> list[AccountSummary]:
        sheet_name = "客户交易结算日报"
        df = self.read_sheet(file_path, sheet_name)
        data_map = self.extract_key_values(df)
        other_fund_map = self.extract_other_fund_details(df)
        trade_date = self.trade_date_from_file(file_path.name)

        total_premium = self.decimal_from_map(data_map, "当日总权利金")
        premium_received, premium_paid = self.split_signed_amount(total_premium)
        balance_c_f = self.decimal_from_map(data_map, "当日结存")
        client_equity = self.decimal_from_map(data_map, "客户权益") or balance_c_f

        account = AccountSummary(
            creation_date=trade_date,
            date_from=trade_date,
            date_to=trade_date,
            client_id=None,
            client_name=self.str_from_map(data_map, "客户名称"),
            account_id=self.str_from_map(data_map, "客户期货期权内部资金账户"),
            currency="CNY",
            balance_b_f=self.decimal_from_map(data_map, "上日结存"),
            deposit_withdrawal=self.decimal_from_map(data_map, "当日存取合计"),
            realized_p_l=self.decimal_from_map(data_map, "当日盈亏"),
            mtm_p_l=self.decimal_from_map(data_map, "持仓盯市盈亏"),
            exercise_p_l=self.decimal_from_map(data_map, "行权盈亏"),
            commission=self.decimal_from_map(data_map, "当日手续费"),
            exercise_fee=abs(other_fund_map.get("行权手续费", Decimal("0"))),
            delivery_fee=other_fund_map.get("交割手续费"),
            premium_received=premium_received,
            premium_paid=premium_paid,
            balance_c_f=balance_c_f,
            client_equity=client_equity,
            pledge_amount=self.decimal_from_map(data_map, "非货币充抵金额"),
            fx_pledge_occ=self.decimal_from_map(data_map, "货币充抵金额"),
            margin_occupied=self.decimal_from_map(data_map, "保证金占用"),
            fund_avail=self.decimal_from_map(data_map, "可用资金"),
            risk_degree=self.percent_from_map(data_map, "风险度"),
            margin_call=self.decimal_from_map(data_map, "追加保证金"),
            source_file=file_path.name,
            raw_payload=self.json_payload(data_map),
        )
        return [account]

    def parse_deposit_withdrawal(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[DepositWithdrawal]:
        sheet_name = "客户交易结算日报"
        df = self.read_sheet(file_path, sheet_name)
        title_row = self.find_section_title_row(df, "期货期权账户出入金明细")
        if title_row is None or title_row + 1 >= len(df):
            return []

        header_row = title_row + 1
        header = self.row_values(df.iloc[header_row])
        rows: list[DepositWithdrawal] = []

        for idx in range(header_row + 1, len(df)):
            values = self.row_values(df.iloc[idx])
            joined = "".join(values).replace(" ", "")
            if not any(values) or "其它资金明细" in joined or "期货持仓汇总" in joined:
                break
            if values[0] == "合计":
                continue

            row = pd.Series(df.iloc[idx].values, index=header)
            deposit = self.get_decimal(row, "入金")
            withdrawal = self.get_decimal(row, "出金")
            if self.is_zero_or_none(deposit) and self.is_zero_or_none(withdrawal):
                continue

            raw_line_no = idx + 1
            rows.append(
                DepositWithdrawal(
                    date=self.date8(self.get_value(row, "发生日期")) or self.trade_date_from_file(file_path.name),
                    type=self.get_text(row, "方式"),
                    deposit=deposit,
                    withdrawal=withdrawal,
                    exchange_rate=None,
                    account_id=account_id,
                    note=self.get_text(row, "摘要"),
                    source_file=file_path.name,
                    source_section="期货期权账户出入金明细",
                    raw_line_no=raw_line_no,
                    row_hash=self.row_hash(file_path.name, sheet_name, raw_line_no, row),
                    raw_payload=self.json_payload(row.to_dict()),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------
    def parse_futures_transactions(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[TransactionRecord]:
        sheet_name = "成交明细"
        df, header_row = self.read_table(file_path, sheet_name, ["合约", "成交序号", "买/卖", "成交价", "开/平"])
        if df is None:
            return []

        rows: list[TransactionRecord] = []
        for idx, row in df.iterrows():
            instrument = self.get_text(row, "合约")
            if not instrument or self.is_summary(instrument):
                continue
            lots = self.get_decimal(row, "手数")
            price = self.get_decimal(row, "成交价")
            if self.is_zero_or_none(lots) or price is None:
                continue

            raw_line_no = int(idx) + header_row + 2
            trade_date = self.date8(self.get_value(row, "实际成交日期")) or self.trade_date_from_file(file_path.name)
            rows.append(
                TransactionRecord(
                    date=trade_date,
                    product=self.product_from_instrument(instrument),
                    instrument=instrument,
                    b_s=self.map_buy_sell(self.get_text(row, "买/卖")),
                    s_h=self.map_hedge(self.get_text(row, "投机（一般）/套保/套利")),
                    price=price,
                    lots=lots,
                    turnover=self.get_decimal(row, "成交额"),
                    o_c=self.map_open_close(self.get_text(row, "开/平")),
                    fee=self.get_decimal(row, "手续费"),
                    realized_p_l=self.get_decimal(row, "平仓盈亏"),
                    premium_received_paid=None,
                    trans_no=self.get_text(row, "成交序号"),
                    account_id=account_id,
                    source_file=file_path.name,
                    sheet_name=sheet_name,
                    raw_line_no=raw_line_no,
                    row_hash=self.row_hash(file_path.name, sheet_name, raw_line_no, row),
                    trade_time=self.get_text(row, "成交时间"),
                    raw_payload=self.json_payload(row.to_dict()),
                )
            )
        return rows

    def parse_option_transactions(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[TransactionRecord]:
        sheet_name = "期权成交明细"
        df, header_row = self.read_table(file_path, sheet_name, ["品种合约", "流水号", "买/卖", "权利金单价", "成交量"])
        if df is None:
            return []

        rows: list[TransactionRecord] = []
        for idx, row in df.iterrows():
            instrument = self.get_text(row, "品种合约")
            if not instrument or self.is_summary(instrument):
                continue
            lots = self.get_decimal(row, "成交量")
            price = self.get_decimal(row, "权利金单价")
            if self.is_zero_or_none(lots) or price is None:
                continue

            raw_line_no = int(idx) + header_row + 2
            premium = self.get_decimal(row, "权利金")
            rows.append(
                TransactionRecord(
                    date=self.date8(self.get_value(row, "成交日期")) or self.trade_date_from_file(file_path.name),
                    product=self.product_from_instrument(instrument),
                    instrument=instrument,
                    b_s=self.map_buy_sell(self.get_text(row, "买/卖")),
                    s_h="一般",
                    price=price,
                    lots=lots,
                    turnover=abs(premium) if premium is not None else None,
                    o_c=None,
                    fee=self.get_decimal(row, "手续费"),
                    realized_p_l=None,
                    premium_received_paid=premium,
                    trans_no=self.get_text(row, "流水号"),
                    account_id=account_id,
                    source_file=file_path.name,
                    sheet_name=sheet_name,
                    raw_line_no=raw_line_no,
                    row_hash=self.row_hash(file_path.name, sheet_name, raw_line_no, row),
                    trade_time=self.get_text(row, "成交时间"),
                    raw_payload=self.json_payload(row.to_dict()),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Close and exercise statements
    # ------------------------------------------------------------------
    def parse_position_closed(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[PositionClosed]:
        sheet_name = "平仓明细"
        df, header_row = self.read_table(file_path, sheet_name, ["合约", "成交序号", "买/卖", "成交价", "开仓价"])
        if df is None:
            return []

        rows: list[PositionClosed] = []
        for idx, row in df.iterrows():
            instrument = self.get_text(row, "合约")
            if not instrument or self.is_summary(instrument):
                continue
            lots = self.get_decimal(row, "手数")
            if self.is_zero_or_none(lots):
                continue
            raw_line_no = int(idx) + header_row + 2
            rows.append(
                PositionClosed(
                    close_date=self.date8(self.get_value(row, "实际成交日期")) or self.trade_date_from_file(file_path.name),
                    product=self.product_from_instrument(instrument),
                    instrument=instrument,
                    b_s=self.map_buy_sell(self.get_text(row, "买/卖")),
                    lots=lots,
                    pos_open_price=self.get_decimal(row, "开仓价"),
                    prev_sttl=self.get_decimal(row, "昨结算价"),
                    trans_price=self.get_decimal(row, "成交价"),
                    realized_p_l=self.get_decimal(row, "平仓盈亏"),
                    account_id=account_id,
                    source_file=file_path.name,
                    sheet_name=sheet_name,
                    raw_line_no=raw_line_no,
                    row_hash=self.row_hash(file_path.name, sheet_name, raw_line_no, row),
                    raw_payload=self.json_payload(row.to_dict()),
                )
            )
        return rows

    def parse_exercise_statement(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[ExerciseStatement]:
        sheet_name = "客户交易结算日报"
        df = self.read_sheet(file_path, sheet_name)
        title_row = self.find_section_title_row(df, "期权行权明细")
        if title_row is None:
            return []

        header_row = None
        for i in range(title_row + 1, min(title_row + 6, len(df))):
            values = self.row_values(df.iloc[i])
            if sum(1 for key in ["交易所", "品种合约", "买/卖", "成交量", "手续费"] if key in values) >= 4:
                header_row = i
                break
        if header_row is None:
            return []

        header = self.row_values(df.iloc[header_row])
        rows: list[ExerciseStatement] = []
        for idx in range(header_row + 1, len(df)):
            row = pd.Series(df.iloc[idx].values, index=header)
            instrument = self.get_text(row, "品种合约")
            if not instrument:
                continue
            if self.is_summary(instrument) or self.get_text(row, "交易所") == "合计":
                break
            lots = self.get_decimal(row, "成交量")
            if self.is_zero_or_none(lots):
                continue
            raw_line_no = idx + 1
            rows.append(
                ExerciseStatement(
                    date=self.date8(self.get_value(row, "行权日期")) or self.trade_date_from_file(file_path.name),
                    exchange=self.get_text(row, "交易所"),
                    product=self.product_from_instrument(instrument),
                    instrument=instrument,
                    b_s=self.map_buy_sell(self.get_text(row, "买/卖")),
                    strike_price=self.get_decimal(row, "执行价"),
                    exercise_price=self.get_decimal(row, "执行价"),
                    lots=lots,
                    turnover=self.get_decimal(row, "行权盈亏"),
                    exercise_p_l=self.get_decimal(row, "行权盈亏"),
                    exercise_fee=self.get_decimal(row, "手续费"),
                    account_id=account_id,
                    source_file=file_path.name,
                    source_section="期权行权明细",
                    raw_line_no=raw_line_no,
                    row_hash=self.row_hash(file_path.name, "期权行权明细", raw_line_no, row),
                    raw_payload=self.json_payload(row.to_dict()),
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------
    def parse_futures_positions_detail(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[PositionsDetail]:
        sheet_name = "持仓明细"
        df, header_row = self.read_table(file_path, sheet_name, ["合约", "买持仓", "卖持仓", "今结算价"])
        if df is None:
            return []

        rows: list[PositionsDetail] = []
        for idx, row in df.iterrows():
            instrument = self.get_text(row, "合约")
            if not instrument or self.is_summary(instrument):
                continue
            raw_line_no = int(idx) + header_row + 2
            common = {
                "date": self.trade_date_from_file(file_path.name),
                "product": self.product_from_instrument(instrument),
                "instrument": instrument,
                "open_date": self.date8(self.get_value(row, "实际成交日期")),
                "s_h": self.map_hedge(self.get_text(row, "投机（一般）/套保/套利")),
                "prev_sttl": self.get_decimal(row, "昨结算价"),
                "settlement_price": self.get_decimal(row, "今结算价"),
                "accum_p_l": self.get_decimal(row, "持仓盈亏"),
                "mtm_p_l": self.get_decimal(row, "持仓盈亏"),
                "account_id": account_id,
                "source_file": file_path.name,
                "source_section": sheet_name,
                "raw_line_no": raw_line_no,
                "row_hash": self.row_hash(file_path.name, sheet_name, raw_line_no, row),
                "raw_payload": self.json_payload(row.to_dict()),
            }
            buy_qty = self.get_decimal(row, "买持仓")
            sell_qty = self.get_decimal(row, "卖持仓")
            if buy_qty and buy_qty > 0:
                rows.append(
                    PositionsDetail(
                        **common,
                        b_s="买",
                        position_qty=buy_qty,
                        pos_open_price=self.get_decimal(row, "买入价"),
                    )
                )
            if sell_qty and sell_qty > 0:
                rows.append(
                    PositionsDetail(
                        **common,
                        b_s="卖",
                        position_qty=sell_qty,
                        pos_open_price=self.get_decimal(row, "卖出价"),
                    )
                )
        return rows

    def parse_option_positions_detail(
        self,
        file_path: Path,
        account_id: str | None,
    ) -> list[PositionsDetail]:
        sheet_name = "客户交易结算日报"
        df = self.read_sheet(file_path, sheet_name)
        title_row = self.find_section_title_row(df, "期权持仓汇总")
        if title_row is None or title_row + 1 >= len(df):
            return []

        header_row = title_row + 1
        header = self.row_values(df.iloc[header_row])
        rows: list[PositionsDetail] = []
        for idx in range(header_row + 1, len(df)):
            values = self.row_values(df.iloc[idx])
            joined = "".join(values).replace(" ", "")
            if not any(values) or "按合同规定" in joined:
                break
            row = pd.Series(df.iloc[idx].values, index=header)
            instrument = self.get_text(row, "品种合约")
            if not instrument or self.is_summary(instrument):
                continue

            raw_line_no = idx + 1
            common = {
                "date": self.trade_date_from_file(file_path.name),
                "trading_code": self.get_text(row, "交易编码"),
                "product": self.product_from_instrument(instrument),
                "instrument": instrument,
                "s_h": "一般",
                "prev_sttl": self.get_decimal(row, "昨结算价"),
                "settlement_price": self.get_decimal(row, "今结算价"),
                "margin": self.get_decimal(row, "交易保证金"),
                "account_id": account_id,
                "source_file": file_path.name,
                "source_section": "期权持仓汇总",
                "raw_line_no": raw_line_no,
                "row_hash": self.row_hash(file_path.name, "期权持仓汇总", raw_line_no, row),
                "raw_payload": self.json_payload(row.to_dict()),
            }
            buy_qty = self.get_decimal(row, "买持仓")
            sell_qty = self.get_decimal(row, "卖持仓")
            if buy_qty and buy_qty > 0:
                rows.append(
                    PositionsDetail(
                        **common,
                        b_s="买",
                        position_qty=buy_qty,
                        pos_open_price=self.get_decimal(row, "买均价"),
                    )
                )
            if sell_qty and sell_qty > 0:
                rows.append(
                    PositionsDetail(
                        **common,
                        b_s="卖",
                        position_qty=sell_qty,
                        pos_open_price=self.get_decimal(row, "卖均价"),
                    )
                )
        return rows

    def aggregate_positions(
        self,
        details: list[PositionsDetail],
        trade_date: str,
        source_file: str,
    ) -> list[Positions]:
        grouped: dict[tuple[str | None, str], list[PositionsDetail]] = defaultdict(list)
        for detail in details:
            if detail.instrument:
                grouped[(detail.account_id, detail.instrument)].append(detail)

        positions: list[Positions] = []
        for (account_id, instrument), items in grouped.items():
            long_items = [x for x in items if x.b_s == "买" and x.position_qty]
            short_items = [x for x in items if x.b_s == "卖" and x.position_qty]
            long_pos = sum((x.position_qty or Decimal("0")) for x in long_items) or None
            short_pos = sum((x.position_qty or Decimal("0")) for x in short_items) or None
            first = items[0]
            positions.append(
                Positions(
                    date=trade_date,
                    trading_code=first.trading_code,
                    product=first.product,
                    instrument=instrument,
                    long_pos=long_pos,
                    avg_buy_price=self.weighted_price(long_items),
                    short_pos=short_pos,
                    avg_sell_price=self.weighted_price(short_items),
                    prev_sttl=first.prev_sttl,
                    sttl_today=first.settlement_price,
                    mtm_p_l=sum((x.mtm_p_l or Decimal("0")) for x in items),
                    margin_occupied=sum((x.margin or Decimal("0")) for x in items) or None,
                    s_h=first.s_h,
                    account_id=account_id,
                    source_file=source_file,
                    source_section="positions_detail",
                    raw_payload=self.json_payload([x.model_dump(mode="json") for x in items]),
                )
            )
        return positions

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate_commission(
        self,
        parsed: dict[str, Any],
        trade_date: str,
        account_id: str | None,
        source_file: str,
    ) -> list[ValidationResult]:
        account_rows = parsed.get("account_summary", [])
        account = account_rows[0] if account_rows else None
        expected = account.commission if account else None
        if expected is None:
            return [
                ValidationResult(
                    check_name="commission_check",
                    status="WARN",
                    details="account commission is missing",
                    source_file=source_file,
                    date=trade_date,
                    account_id=account_id,
                )
            ]

        transaction_fee = sum((row.fee or Decimal("0")) for row in parsed.get("transaction_record", []))
        exercise_fee = sum((row.exercise_fee or Decimal("0")) for row in parsed.get("exercise_statement", []))
        actual = transaction_fee + exercise_fee
        diff = actual - expected
        status = "PASS" if abs(diff) <= Decimal("0.01") else "FAIL"
        return [
            ValidationResult(
                check_name="commission_check",
                status=status,
                actual_value=str(actual),
                expected_value=str(expected),
                diff_value=str(diff),
                tolerance="0.01",
                details=f"transaction_fee={transaction_fee}, exercise_fee={exercise_fee}",
                source_file=source_file,
                date=trade_date,
                account_id=account_id,
                is_blocking=status == "FAIL",
            )
        ]

    # ------------------------------------------------------------------
    # Shared readers and value helpers
    # ------------------------------------------------------------------
    def read_sheet(self, file_path: Path, sheet_name: str) -> pd.DataFrame:
        return pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    def read_table(
        self,
        file_path: Path,
        sheet_name: str,
        keywords: list[str],
    ) -> tuple[pd.DataFrame | None, int]:
        try:
            raw = self.read_sheet(file_path, sheet_name)
        except Exception:
            return None, -1
        header_row = self.find_header_row(raw, keywords)
        if header_row is None:
            return None, -1
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row, dtype=str)
        df = df.dropna(how="all")
        df.columns = [str(c).strip() if not pd.isna(c) else "" for c in df.columns]
        return df, header_row

    def find_header_row(self, raw: pd.DataFrame, keywords: list[str]) -> int | None:
        for i in range(len(raw)):
            values = self.row_values(raw.iloc[i])
            if sum(1 for key in keywords if key in values) >= min(3, len(keywords)):
                return i
        return None

    def find_section_title_row(self, raw: pd.DataFrame, title_keyword: str) -> int | None:
        for i in range(len(raw)):
            joined = "".join(self.row_values(raw.iloc[i])).replace(" ", "")
            if title_keyword in joined:
                return i
        return None

    def extract_key_values(self, df: pd.DataFrame) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for i in range(len(df)):
            row = df.iloc[i]
            for j in range(len(row)):
                key = row.iat[j]
                if pd.isna(key):
                    continue
                key_text = str(key).strip()
                if not key_text:
                    continue
                for k in range(j + 1, len(row)):
                    value = row.iat[k]
                    if not pd.isna(value):
                        result[key_text] = value
                        break
        return result

    def extract_other_fund_details(self, df: pd.DataFrame) -> dict[str, Decimal]:
        result: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        title_row = self.find_section_title_row(df, "其它资金明细")
        if title_row is None or title_row + 1 >= len(df):
            return dict(result)
        header = self.row_values(df.iloc[title_row + 1])
        if "类型" not in header or "金额" not in header:
            return dict(result)
        for idx in range(title_row + 2, min(title_row + 20, len(df))):
            values = self.row_values(df.iloc[idx])
            if not any(values):
                break
            row = pd.Series(df.iloc[idx].values, index=header)
            fee_type = self.get_text(row, "类型")
            if not fee_type or fee_type == "合计":
                continue
            amount = self.get_decimal(row, "金额")
            if amount is not None:
                result[fee_type] += amount
        return dict(result)

    def row_values(self, row: pd.Series) -> list[str]:
        return ["" if pd.isna(v) else str(v).strip() for v in row.tolist()]

    def get_value(self, row: pd.Series, column_name: str) -> Any:
        if column_name not in row.index:
            return None
        value = row[column_name]
        if pd.isna(value):
            return None
        return value

    def get_text(self, row: pd.Series, column_name: str) -> str | None:
        value = self.get_value(row, column_name)
        if value is None:
            return None
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        return text or None

    def get_decimal(self, row: pd.Series, column_name: str) -> Decimal | None:
        return self.to_decimal(self.get_value(row, column_name))

    def to_decimal(self, value: Any) -> Decimal | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).replace(",", "").replace("%", "").strip()
        if text in {"", "--", "nan", "None"}:
            return None
        try:
            return Decimal(text)
        except Exception:
            return None

    def decimal_from_map(self, data_map: dict[str, Any], key: str) -> Decimal | None:
        key_norm = self.normalize_text(key)
        for current_key, value in data_map.items():
            if key_norm in self.normalize_text(current_key):
                return self.to_decimal(value)
        return None

    def str_from_map(self, data_map: dict[str, Any], key: str) -> str | None:
        key_norm = self.normalize_text(key)
        for current_key, value in data_map.items():
            if key_norm in self.normalize_text(current_key):
                text = str(value).strip()
                if text.endswith(".0"):
                    text = text[:-2]
                return text or None
        return None

    def percent_from_map(self, data_map: dict[str, Any], key: str) -> Decimal | None:
        return self.decimal_from_map(data_map, key)

    def normalize_text(self, value: Any) -> str:
        return str(value).replace(" ", "").replace("：", "").replace(":", "").strip()

    def is_zero_or_none(self, value: Decimal | None) -> bool:
        return value is None or value == 0

    def is_summary(self, text: str) -> bool:
        return any(keyword in str(text) for keyword in ["合计", "小计", "总计", "基本资料"])

    def date8(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        match = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", text)
        if match:
            return "".join(match.groups())
        try:
            return pd.to_datetime(value).strftime("%Y%m%d")
        except Exception:
            return None

    def trade_date_from_file(self, filename: str) -> str:
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
        if not match:
            raise ValueError(f"无法从文件名提取交易日期: {filename}")
        return "".join(match.groups())

    def map_buy_sell(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        mapping = {
            "买": "买",
            "卖": "卖",
            "Buy": "买",
            "Sell": "卖",
            "B": "买",
            "S": "卖",
        }
        return mapping.get(value, value)

    def map_open_close(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        mapping = {
            "开": "开",
            "平": "平",
            "平仓": "平",
            "平今": "平今",
            "平昨": "平昨",
            "Close Today": "平今",
            "Close Prev.": "平昨",
            "Open": "开",
            "Close": "平",
        }
        return mapping.get(value, value)

    def map_hedge(self, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        mapping = {
            "投机": "投机",
            "一般": "一般",
            "套保": "套保",
            "套利": "套利",
            "Speculation": "投机",
            "General": "一般",
            "Hedge": "套保",
            "Arbitrage": "套利",
        }
        return mapping.get(value, value)

    def product_from_instrument(self, instrument: str | None) -> str | None:
        if not instrument:
            return None
        match = re.match(r"([A-Za-z]+)", instrument)
        return match.group(1).upper() if match else None

    def weighted_price(self, items: list[PositionsDetail]) -> Decimal | None:
        total_qty = sum((x.position_qty or Decimal("0")) for x in items)
        if total_qty == 0:
            return None
        total_amount = sum((x.position_qty or Decimal("0")) * (x.pos_open_price or Decimal("0")) for x in items)
        return total_amount / total_qty

    def split_signed_amount(self, amount: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
        if amount is None:
            return None, None
        if amount >= 0:
            return amount, Decimal("0")
        return Decimal("0"), abs(amount)

    def row_hash(self, source_file: str, sheet_name: str | None, raw_line_no: int | None, row: pd.Series) -> str:
        parts = [source_file or "", sheet_name or "", str(raw_line_no or "")]
        for key, value in row.items():
            if pd.isna(value):
                text = ""
            else:
                text = str(value).strip()
            parts.append(f"{key}={text}")
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def json_payload(self, value: Any) -> str:
        def default(obj: Any) -> str:
            return str(obj)

        return json.dumps(value, ensure_ascii=False, default=default)
