from collections import defaultdict, deque
from datetime import datetime, time
from decimal import Decimal

from app.models import FifoMatch, PositionLot, PositionSnapshot, TradeExecution, ValidationIssue


def _trade_sort_key(trade: TradeExecution):
    trade_time = trade.trade_time or datetime.combine(trade.trade_date, time.min)
    return (
        trade.trade_date,
        trade_time,
        trade.raw_line_no or 0,
    )


def _open_lot_direction(trade: TradeExecution) -> str | None:
    if trade.open_close != "open":
        return None
    if trade.direction == "buy":
        return "long"
    if trade.direction == "sell":
        return "short"
    return None


def _close_lot_direction(trade: TradeExecution) -> str | None:
    if trade.open_close not in {"close", "close_today", "close_yesterday"}:
        return None
    if trade.direction == "sell":
        return "long"
    if trade.direction == "buy":
        return "short"
    return None


def _lot_key(account_id: str | None, instrument_code: str, direction: str):
    return account_id, instrument_code, direction


def generate_fifo(
    trades: list[TradeExecution],
    positions: list[PositionSnapshot],
    source_file: str | None = None,
) -> tuple[list[FifoMatch], list[PositionLot], list[ValidationIssue]]:
    lots: dict[tuple, deque[dict]] = defaultdict(deque)
    matches: list[FifoMatch] = []
    issues: list[ValidationIssue] = []

    for trade in sorted(trades, key=_trade_sort_key):
        open_direction = _open_lot_direction(trade)
        close_direction = _close_lot_direction(trade)

        if open_direction:
            key = _lot_key(trade.account_id, trade.instrument_code, open_direction)
            lots[key].append(
                {
                    "trade_date": trade.trade_date,
                    "account_id": trade.account_id,
                    "instrument_code": trade.instrument_code,
                    "asset_type": trade.asset_type,
                    "direction": open_direction,
                    "volume": trade.volume,
                    "remaining_volume": trade.volume,
                    "open_price": trade.price,
                    "open_time": trade.trade_time,
                    "source_file": trade.source_file,
                    "source_type": "trade",
                    "source_reason": None,
                    "open_trade_row_hash": trade.row_hash,
                }
            )
            continue

        if not close_direction:
            continue

        key = _lot_key(trade.account_id, trade.instrument_code, close_direction)
        remaining_to_close = trade.volume

        if not lots[key]:
            lots[key].append(
                {
                    "trade_date": trade.trade_date,
                    "account_id": trade.account_id,
                    "instrument_code": trade.instrument_code,
                    "asset_type": trade.asset_type,
                    "direction": close_direction,
                    "volume": remaining_to_close,
                    "remaining_volume": remaining_to_close,
                    "open_price": trade.price,
                    "open_time": trade.trade_time,
                    "source_file": trade.source_file,
                    "source_type": "seed",
                    "source_reason": "missing_history_for_close",
                    "open_trade_row_hash": f"seed:{trade.row_hash}",
                }
            )

        while remaining_to_close > 0:
            if not lots[key]:
                issues.append(
                    ValidationIssue(
                        trade_date=trade.trade_date,
                        account_id=trade.account_id,
                        source_file=source_file or trade.source_file,
                        check_name="fifo_close_volume",
                        message=f"{trade.instrument_code} close volume exceeds available lots",
                        expected_value=str(trade.volume),
                        actual_value=str(trade.volume - remaining_to_close),
                    )
                )
                break

            lot = lots[key][0]
            matched_volume = min(remaining_to_close, lot["remaining_volume"])
            pnl_sign = Decimal("1") if close_direction == "long" else Decimal("-1")
            realized_pnl = (trade.price - lot["open_price"]) * Decimal(str(matched_volume)) * pnl_sign

            matches.append(
                FifoMatch(
                    trade_date=trade.trade_date,
                    account_id=trade.account_id,
                    instrument_code=trade.instrument_code,
                    asset_type=trade.asset_type,
                    direction=close_direction,
                    open_trade_row_hash=lot["open_trade_row_hash"],
                    close_trade_row_hash=trade.row_hash,
                    volume=matched_volume,
                    open_price=lot["open_price"],
                    close_price=trade.price,
                    realized_pnl=realized_pnl,
                    source_file=source_file or trade.source_file,
                )
            )

            lot["remaining_volume"] -= matched_volume
            remaining_to_close -= matched_volume
            if lot["remaining_volume"] <= 0:
                lots[key].popleft()

    expected_positions = {
        _lot_key(pos.account_id, pos.instrument_code, pos.direction): pos
        for pos in positions
        if pos.direction in {"long", "short"} and pos.open_interest > 0
    }

    for key, pos in expected_positions.items():
        current_qty = sum(lot["remaining_volume"] for lot in lots.get(key, []))
        if current_qty < pos.open_interest:
            adjustment_volume = pos.open_interest - current_qty
            lots[key].append(
                {
                    "trade_date": pos.trade_date,
                    "account_id": pos.account_id,
                    "instrument_code": pos.instrument_code,
                    "asset_type": pos.asset_type,
                    "direction": pos.direction,
                    "volume": adjustment_volume,
                    "remaining_volume": adjustment_volume,
                    "open_price": pos.avg_open_price or pos.settlement_price or Decimal("0"),
                    "open_time": None,
                    "source_file": pos.source_file,
                    "source_type": "adjustment",
                    "source_reason": "reconcile_to_statement_position",
                    "open_trade_row_hash": f"adjustment:{pos.source_file}:{pos.instrument_code}:{pos.direction}",
                }
            )
        elif current_qty > pos.open_interest:
            issues.append(
                ValidationIssue(
                    trade_date=pos.trade_date,
                    account_id=pos.account_id,
                    source_file=source_file or pos.source_file,
                    check_name="fifo_ending_position",
                    message=f"{pos.instrument_code} FIFO ending lots exceed statement position",
                    expected_value=str(pos.open_interest),
                    actual_value=str(current_qty),
                )
            )

    position_lots: list[PositionLot] = []
    for lot_queue in lots.values():
        for lot in lot_queue:
            if lot["remaining_volume"] <= 0:
                continue
            position_lots.append(PositionLot(**lot))

    return matches, position_lots, issues
