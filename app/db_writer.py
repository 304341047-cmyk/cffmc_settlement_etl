from __future__ import annotations

from sqlalchemy import func, text

from app.db.base import SessionLocal
from app.db.models import (
    AccountSummaryDB,
    DepositWithdrawalDB,
    ExerciseStatementDB,
    FifoMatchDB,
    FifoPositionDB,
    PositionClosedDB,
    PositionLotDB,
    PositionsDB,
    PositionsDetailDB,
    SourceFileRecordDB,
    TransactionRecordDB,
    ValidationResultDB,
)
from app.models import PositionLot
from app.services.fifo import generate_fifo


class BlockingValidationError(Exception):
    pass


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def save_to_db(result: dict):
    session = SessionLocal()
    counters = {
        "inserted_account_summary": 0,
        "inserted_deposit_withdrawal": 0,
        "inserted_transaction_record": 0,
        "inserted_exercise_statement": 0,
        "inserted_position_closed": 0,
        "inserted_positions_detail": 0,
        "inserted_positions": 0,
        "inserted_fifo_matches": 0,
        "inserted_position_lots": 0,
        "inserted_fifo_positions": 0,
        "inserted_validation_result": 0,
    }

    try:
        source_file = guess_source_file(result)
        account_id = guess_account_id(result)
        trade_date = guess_trade_date(result)
        opening_lots = load_opening_lots(session, account_id, trade_date)

        fifo_matches, position_lots, fifo_positions, fifo_validation = generate_fifo(
            trades=result.get("transaction_record", []),
            statement_positions=result.get("positions", []),
            opening_lots=opening_lots,
            source_file=source_file,
        )
        result["fifo_matches"] = fifo_matches
        result["position_lots"] = position_lots
        result["fifo_positions"] = fifo_positions
        result.setdefault("validation_result", []).extend(fifo_validation)

        blocking_failures = [
            row for row in result.get("validation_result", [])
            if row.status == "FAIL" and row.is_blocking
        ]
        if blocking_failures:
            for validation in result.get("validation_result", []):
                session.add(ValidationResultDB(**_dump_model(validation)))
                counters["inserted_validation_result"] += 1
            session.commit()
            details = "; ".join(row.details or row.check_name for row in blocking_failures)
            raise BlockingValidationError(details)

        for row in result.get("account_summary", []):
            session.add(AccountSummaryDB(**_dump_model(row)))
            counters["inserted_account_summary"] += 1

        for row in result.get("deposit_withdrawal", []):
            session.add(DepositWithdrawalDB(**_dump_model(row)))
            counters["inserted_deposit_withdrawal"] += 1

        for row in result.get("transaction_record", []):
            session.add(TransactionRecordDB(**_dump_model(row)))
            counters["inserted_transaction_record"] += 1

        for row in result.get("exercise_statement", []):
            session.add(ExerciseStatementDB(**_dump_model(row)))
            counters["inserted_exercise_statement"] += 1

        for row in result.get("position_closed", []):
            session.add(PositionClosedDB(**_dump_model(row)))
            counters["inserted_position_closed"] += 1

        for row in result.get("positions_detail", []):
            session.add(PositionsDetailDB(**_dump_model(row)))
            counters["inserted_positions_detail"] += 1

        for row in result.get("positions", []):
            session.add(PositionsDB(**_dump_model(row)))
            counters["inserted_positions"] += 1

        for row in result.get("fifo_matches", []):
            session.add(FifoMatchDB(**_dump_model(row)))
            counters["inserted_fifo_matches"] += 1

        for row in result.get("position_lots", []):
            session.add(PositionLotDB(**_dump_model(row)))
            counters["inserted_position_lots"] += 1

        for row in result.get("fifo_positions", []):
            session.add(FifoPositionDB(**_dump_model(row)))
            counters["inserted_fifo_positions"] += 1

        for row in result.get("validation_result", []):
            session.add(ValidationResultDB(**_dump_model(row)))
            counters["inserted_validation_result"] += 1

        session.commit()
        return counters

    except BlockingValidationError:
        raise

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def load_opening_lots(session, account_id: str | None, trade_date: str | None) -> list[PositionLot]:
    if not trade_date:
        return []

    query = session.query(func.max(PositionLotDB.date))
    if account_id:
        query = query.filter(PositionLotDB.account_id == account_id)
    latest_date = query.filter(PositionLotDB.date < trade_date).scalar()
    if not latest_date:
        return []

    rows_query = session.query(PositionLotDB).filter(PositionLotDB.date == latest_date)
    if account_id:
        rows_query = rows_query.filter(PositionLotDB.account_id == account_id)

    rows: list[PositionLot] = []
    for row in rows_query.all():
        rows.append(
            PositionLot(
                date=row.date,
                account_id=row.account_id,
                instrument=row.instrument,
                b_s=row.b_s,
                lots=row.lots,
                remaining_volume=row.remaining_volume,
                pos_open_price=row.pos_open_price,
                open_time=row.open_time,
                source_file=row.source_file,
                source_type=row.source_type,
                source_reason=row.source_reason,
                open_trade_row_hash=row.open_trade_row_hash,
            )
        )
    return rows


def save_validation_results(result: dict):
    session = SessionLocal()
    try:
        count = 0
        for row in result.get("validation_result", []):
            session.add(ValidationResultDB(**_dump_model(row)))
            count += 1
        session.commit()
        return count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_source_file_record(
    file_name: str,
    file_path: str,
    file_hash: str,
    parser_name: str | None,
    status: str,
    error_message: str | None = None,
):
    session = SessionLocal()
    try:
        existing = session.query(SourceFileRecordDB).filter(
            SourceFileRecordDB.file_md5 == file_hash,
        ).first()
        process_status = "SUCCESS" if status.lower() == "success" else "FAILED"
        if existing:
            existing.source_file = file_name
            existing.parser_name = parser_name
            existing.process_status = process_status
            existing.error_message = error_message
        else:
            session.add(
                SourceFileRecordDB(
                    source_file=file_name,
                    file_md5=file_hash,
                    parser_name=parser_name,
                    process_status=process_status,
                    error_message=error_message,
                )
            )
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def is_file_already_processed(file_hash: str) -> bool:
    session = SessionLocal()
    try:
        exists = session.query(SourceFileRecordDB).filter(
            SourceFileRecordDB.file_md5 == file_hash,
            SourceFileRecordDB.process_status == "SUCCESS",
        ).first()
        return exists is not None
    finally:
        session.close()


def create_chinese_query_views(engine):
    view_sql = [
        "CREATE VIEW IF NOT EXISTS 资金状况表 AS SELECT * FROM account_summary",
        "CREATE VIEW IF NOT EXISTS 出入金流水表 AS SELECT * FROM deposit_withdrawal",
        "CREATE VIEW IF NOT EXISTS 原始成交明细表 AS SELECT * FROM transaction_record",
        "CREATE VIEW IF NOT EXISTS 行权明细表 AS SELECT * FROM exercise_statement",
        "CREATE VIEW IF NOT EXISTS 平仓明细表 AS SELECT * FROM position_closed",
        "CREATE VIEW IF NOT EXISTS 持仓明细表 AS SELECT * FROM positions_detail",
        "CREATE VIEW IF NOT EXISTS 持仓汇总表 AS SELECT * FROM positions",
        "CREATE VIEW IF NOT EXISTS FIFO开平匹配表 AS SELECT * FROM fifo_matches",
        "CREATE VIEW IF NOT EXISTS FIFO剩余持仓表 AS SELECT * FROM position_lots",
        "CREATE VIEW IF NOT EXISTS FIFO持仓汇总表 AS SELECT * FROM fifo_positions",
        "CREATE VIEW IF NOT EXISTS 校验结果表 AS SELECT * FROM validation_result",
    ]

    with engine.begin() as connection:
        for sql in view_sql:
            connection.execute(text(sql))


def guess_source_file(result: dict) -> str:
    for key in [
        "account_summary",
        "transaction_record",
        "positions",
        "positions_detail",
        "deposit_withdrawal",
    ]:
        rows = result.get(key, [])
        if rows:
            return getattr(rows[0], "source_file", "") or ""
    return ""


def guess_account_id(result: dict) -> str | None:
    for key in [
        "account_summary",
        "transaction_record",
        "positions",
        "positions_detail",
    ]:
        rows = result.get(key, [])
        if rows:
            account_id = getattr(rows[0], "account_id", None)
            if account_id:
                return account_id
    return None


def guess_trade_date(result: dict) -> str | None:
    account_rows = result.get("account_summary", [])
    if account_rows and getattr(account_rows[0], "date_to", None):
        return account_rows[0].date_to
    for key in ["transaction_record", "positions", "positions_detail"]:
        rows = result.get(key, [])
        if rows:
            date_value = getattr(rows[0], "date", None)
            if date_value:
                return date_value
    return None
