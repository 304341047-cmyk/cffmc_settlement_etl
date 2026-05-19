from __future__ import annotations

from collections import defaultdict, deque
from decimal import Decimal

from app.models import FifoMatch, FifoPosition, PositionLot, Positions, TransactionRecord, ValidationResult


def generate_fifo(
    trades: list[TransactionRecord],
    statement_positions: list[Positions],
    opening_lots: list[PositionLot] | None = None,
    source_file: str = "",
) -> tuple[list[FifoMatch], list[PositionLot], list[FifoPosition], list[ValidationResult]]:
    lots: dict[tuple[str | None, str, str], deque[dict]] = defaultdict(deque)
    matches: list[FifoMatch] = []
    issues: list[ValidationResult] = []
    target_positions = statement_target_map(statement_positions)

    for lot in opening_lots or []:
        if lot.remaining_volume and lot.remaining_volume > 0:
            lots[(lot.account_id, lot.instrument, lot.b_s)].append(lot.model_dump())

    for trade in sorted(trades, key=trade_sort_key):
        qty = to_decimal(trade.lots)
        if not trade.instrument or not trade.b_s or qty <= 0:
            continue

        if trade.o_c == "开":
            append_open_lot(lots, trade, trade.b_s, qty, source_file)
            continue

        if trade.o_c in {"平", "平今", "平昨"}:
            close_side = "买" if trade.b_s == "卖" else "卖"
            consume_lots(lots, matches, issues, trade, close_side, qty, source_file)
            continue

        # CFFMC option transaction rows do not expose O/C. From a zero-position
        # start, strict FIFO can still derive positions by closing opposite lots
        # first and opening the remaining quantity.
        opposite_side = "卖" if trade.b_s == "买" else "买"
        remaining = consume_lots(lots, matches, issues, trade, opposite_side, qty, source_file, allow_shortfall=True)
        if remaining > 0:
            key = lot_key(trade.account_id, trade.instrument, trade.b_s)
            current_qty = current_lot_qty(lots, key)
            target_qty = target_positions.get(key, Decimal("0"))
            open_qty = min(remaining, max(Decimal("0"), target_qty - current_qty))
            if open_qty > 0:
                append_open_lot(lots, trade, trade.b_s, open_qty, source_file)

    ending_lots = flatten_lots(lots, source_file)
    fifo_positions = aggregate_fifo_positions(ending_lots, source_file)
    issues.extend(reconcile_positions(statement_positions, fifo_positions, source_file))

    if not any(issue.status == "FAIL" and issue.is_blocking for issue in issues):
        account_id = statement_positions[0].account_id if statement_positions else (trades[0].account_id if trades else None)
        date = statement_positions[0].date if statement_positions else (trades[0].date if trades else None)
        issues.append(
            ValidationResult(
                check_name="fifo_position_reconcile",
                status="PASS",
                actual_value=str(len(fifo_positions)),
                expected_value=str(len(statement_positions)),
                diff_value="0",
                tolerance="0",
                details="FIFO ending positions match statement positions",
                source_file=source_file,
                date=date,
                account_id=account_id,
                is_blocking=False,
            )
        )

    return matches, ending_lots, fifo_positions, issues


def trade_sort_key(trade: TransactionRecord):
    return (
        trade.date or "",
        trade.trade_time or "",
        trade.raw_line_no or 0,
    )


def to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def lot_key(account_id: str | None, instrument: str, b_s: str):
    return account_id, instrument, b_s


def append_open_lot(
    lots: dict[tuple[str | None, str, str], deque[dict]],
    trade: TransactionRecord,
    b_s: str,
    qty: Decimal,
    source_file: str,
) -> None:
    lots[lot_key(trade.account_id, trade.instrument, b_s)].append(
        {
            "date": trade.date,
            "account_id": trade.account_id,
            "instrument": trade.instrument,
            "b_s": b_s,
            "lots": qty,
            "remaining_volume": qty,
            "pos_open_price": trade.price,
            "open_time": trade.trade_time,
            "source_file": source_file or trade.source_file,
            "source_type": "trade",
            "source_reason": None,
            "open_trade_row_hash": trade.row_hash,
        }
    )


def consume_lots(
    lots: dict[tuple[str | None, str, str], deque[dict]],
    matches: list[FifoMatch],
    issues: list[ValidationResult],
    trade: TransactionRecord,
    close_side: str,
    qty: Decimal,
    source_file: str,
    allow_shortfall: bool = False,
) -> Decimal:
    key = lot_key(trade.account_id, trade.instrument, close_side)
    remaining = qty

    while remaining > 0 and lots.get(key):
        lot = lots[key][0]
        lot_remaining = to_decimal(lot.get("remaining_volume"))
        matched = min(remaining, lot_remaining)
        pnl_sign = Decimal("1") if close_side == "买" else Decimal("-1")
        open_price = to_decimal(lot.get("pos_open_price"))
        close_price = to_decimal(trade.price)
        realized = (close_price - open_price) * matched * pnl_sign

        matches.append(
            FifoMatch(
                date=trade.date,
                account_id=trade.account_id,
                instrument=trade.instrument,
                b_s=close_side,
                open_trade_row_hash=lot.get("open_trade_row_hash"),
                close_trade_row_hash=trade.row_hash,
                lots=matched,
                open_price=open_price,
                close_price=close_price,
                realized_p_l=realized,
                source_file=source_file or trade.source_file,
            )
        )

        lot["remaining_volume"] = lot_remaining - matched
        remaining -= matched
        if lot["remaining_volume"] <= 0:
            lots[key].popleft()

    if remaining > 0 and not allow_shortfall:
        issues.append(
            ValidationResult(
                check_name="fifo_close_without_open_lot",
                status="FAIL",
                actual_value=str(qty - remaining),
                expected_value=str(qty),
                diff_value=str(remaining),
                tolerance="0",
                details=f"{trade.instrument} {trade.b_s}{trade.o_c or ''} has no available {close_side} FIFO lot",
                source_file=source_file or trade.source_file,
                date=trade.date,
                account_id=trade.account_id,
                is_blocking=True,
            )
        )

    return remaining


def flatten_lots(lots: dict[tuple[str | None, str, str], deque[dict]], source_file: str) -> list[PositionLot]:
    result: list[PositionLot] = []
    for lot_queue in lots.values():
        for lot in lot_queue:
            remaining = to_decimal(lot.get("remaining_volume"))
            if remaining <= 0:
                continue
            snapshot = dict(lot)
            snapshot["date"] = source_date(source_file) or snapshot.get("date")
            snapshot["source_file"] = source_file or snapshot.get("source_file")
            snapshot["remaining_volume"] = remaining
            result.append(PositionLot(**snapshot))
    return result


def aggregate_fifo_positions(lots: list[PositionLot], source_file: str) -> list[FifoPosition]:
    grouped: dict[tuple[str | None, str, str], list[PositionLot]] = defaultdict(list)
    for lot in lots:
        grouped[(lot.account_id, lot.instrument, lot.b_s)].append(lot)

    positions: list[FifoPosition] = []
    for (account_id, instrument, b_s), group in grouped.items():
        qty = sum((lot.remaining_volume or Decimal("0")) for lot in group)
        if qty <= 0:
            continue
        amount = sum((lot.remaining_volume or Decimal("0")) * (lot.pos_open_price or Decimal("0")) for lot in group)
        positions.append(
            FifoPosition(
                date=group[0].date,
                account_id=account_id,
                instrument=instrument,
                b_s=b_s,
                lots=qty,
                avg_open_price=amount / qty if qty else None,
                source_file=source_file,
            )
        )
    return positions


def current_lot_qty(lots: dict[tuple[str | None, str, str], deque[dict]], key: tuple[str | None, str, str]) -> Decimal:
    return sum((to_decimal(lot.get("remaining_volume")) for lot in lots.get(key, [])), Decimal("0"))


def statement_target_map(statement_positions: list[Positions]) -> dict[tuple[str | None, str, str], Decimal]:
    expected: dict[tuple[str | None, str, str], Decimal] = defaultdict(Decimal)
    for pos in statement_positions:
        if not pos.instrument:
            continue
        if pos.long_pos and pos.long_pos > 0:
            expected[(pos.account_id, pos.instrument, "买")] += pos.long_pos
        if pos.short_pos and pos.short_pos > 0:
            expected[(pos.account_id, pos.instrument, "卖")] += pos.short_pos
    return expected


def reconcile_positions(
    statement_positions: list[Positions],
    fifo_positions: list[FifoPosition],
    source_file: str,
) -> list[ValidationResult]:
    expected = statement_target_map(statement_positions)

    actual: dict[tuple[str | None, str, str], Decimal] = defaultdict(Decimal)
    for pos in fifo_positions:
        actual[(pos.account_id, pos.instrument, pos.b_s)] += pos.lots

    issues: list[ValidationResult] = []
    date = statement_positions[0].date if statement_positions else (fifo_positions[0].date if fifo_positions else source_date(source_file))
    account_id = statement_positions[0].account_id if statement_positions else (fifo_positions[0].account_id if fifo_positions else None)

    for key in sorted(set(expected) | set(actual), key=lambda item: (item[0] or "", item[1], item[2])):
        expected_qty = expected.get(key, Decimal("0"))
        actual_qty = actual.get(key, Decimal("0"))
        diff = actual_qty - expected_qty
        if diff == 0:
            continue
        _, instrument, b_s = key
        issues.append(
            ValidationResult(
                check_name="fifo_position_reconcile",
                status="FAIL",
                actual_value=str(actual_qty),
                expected_value=str(expected_qty),
                diff_value=str(diff),
                tolerance="0",
                details=f"{instrument} {b_s} FIFO ending position does not match statement",
                source_file=source_file,
                date=date,
                account_id=account_id,
                is_blocking=True,
            )
        )
    return issues


def source_date(source_file: str) -> str | None:
    import re

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", source_file or "")
    if not match:
        return None
    return "".join(match.groups())
