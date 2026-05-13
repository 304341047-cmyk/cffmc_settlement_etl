from sqlalchemy import text

from app.db.base import SessionLocal
from app.db.models import (
    AccountDailySnapshotDB,
    CashFlowDB,
    CloseDetailDB,
    FifoMatchDB,
    OptionExerciseDetailDB,
    PositionDetailDB,
    PositionLotDB,
    PositionSnapshotDB,
    SourceFileDB,
    TradeExecutionDB,
    TradeSummaryDB,
    ValidationIssueDB,
)


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def save_to_db(result: dict):
    session = SessionLocal()

    counters = {
        "inserted_trades": 0,
        "inserted_cash_flows": 0,
        "inserted_trade_summaries": 0,
        "inserted_close_details": 0,
        "inserted_position_details": 0,
        "inserted_positions": 0,
        "inserted_accounts": 0,
        "inserted_exercise_details": 0,
        "inserted_fifo_matches": 0,
        "inserted_position_lots": 0,
        "inserted_validation_issues": 0,
    }

    try:
        for trade in result.get("trades", []):
            exists = session.query(TradeExecutionDB).filter(
                TradeExecutionDB.source_file == trade.source_file,
                TradeExecutionDB.sheet_name == trade.sheet_name,
                TradeExecutionDB.raw_line_no == trade.raw_line_no,
                TradeExecutionDB.row_hash == trade.row_hash,
            ).first()
            if exists:
                continue
            session.add(TradeExecutionDB(**_dump_model(trade)))
            counters["inserted_trades"] += 1

        for flow in result.get("cash_flows", []):
            exists = session.query(CashFlowDB).filter(
                CashFlowDB.source_file == flow.source_file,
                CashFlowDB.source_section == flow.source_section,
                CashFlowDB.raw_line_no == flow.raw_line_no,
                CashFlowDB.row_hash == flow.row_hash,
            ).first()
            if exists:
                continue
            session.add(CashFlowDB(**_dump_model(flow)))
            counters["inserted_cash_flows"] += 1

        for summary in result.get("trade_summaries", []):
            exists = session.query(TradeSummaryDB).filter(
                TradeSummaryDB.source_file == summary.source_file,
                TradeSummaryDB.source_section == summary.source_section,
                TradeSummaryDB.raw_line_no == summary.raw_line_no,
                TradeSummaryDB.row_hash == summary.row_hash,
            ).first()
            if exists:
                continue
            session.add(TradeSummaryDB(**_dump_model(summary)))
            counters["inserted_trade_summaries"] += 1

        for close in result.get("close_details", []):
            exists = session.query(CloseDetailDB).filter(
                CloseDetailDB.source_file == close.source_file,
                CloseDetailDB.sheet_name == close.sheet_name,
                CloseDetailDB.raw_line_no == close.raw_line_no,
                CloseDetailDB.row_hash == close.row_hash,
            ).first()
            if exists:
                continue
            session.add(CloseDetailDB(**_dump_model(close)))
            counters["inserted_close_details"] += 1

        for pos in result.get("position_details", []):
            exists = session.query(PositionDetailDB).filter(
                PositionDetailDB.trade_date == pos.trade_date,
                PositionDetailDB.account_id == pos.account_id,
                PositionDetailDB.instrument_code == pos.instrument_code,
                PositionDetailDB.direction == pos.direction,
                PositionDetailDB.source_file == pos.source_file,
                PositionDetailDB.source_section == pos.source_section,
                PositionDetailDB.raw_line_no == pos.raw_line_no,
            ).first()
            if exists:
                continue
            session.add(PositionDetailDB(**_dump_model(pos)))
            counters["inserted_position_details"] += 1

        for pos in result.get("positions", []):
            exists = session.query(PositionSnapshotDB).filter(
                PositionSnapshotDB.trade_date == pos.trade_date,
                PositionSnapshotDB.account_id == pos.account_id,
                PositionSnapshotDB.instrument_code == pos.instrument_code,
                PositionSnapshotDB.direction == pos.direction,
                PositionSnapshotDB.source_file == pos.source_file,
            ).first()
            if exists:
                continue
            session.add(PositionSnapshotDB(**_dump_model(pos)))
            counters["inserted_positions"] += 1

        for ex in result.get("exercise_details", []):
            exists = session.query(OptionExerciseDetailDB).filter(
                OptionExerciseDetailDB.trade_date == ex.trade_date,
                OptionExerciseDetailDB.account_id == ex.account_id,
                OptionExerciseDetailDB.exchange == ex.exchange,
                OptionExerciseDetailDB.instrument_code == ex.instrument_code,
                OptionExerciseDetailDB.direction == ex.direction,
                OptionExerciseDetailDB.quantity == ex.quantity,
                OptionExerciseDetailDB.source_file == ex.source_file,
                OptionExerciseDetailDB.raw_line_no == ex.raw_line_no,
            ).first()
            if exists:
                continue
            session.add(OptionExerciseDetailDB(**_dump_model(ex)))
            counters["inserted_exercise_details"] += 1

        for match in result.get("fifo_matches", []):
            exists = session.query(FifoMatchDB).filter(
                FifoMatchDB.source_file == match.source_file,
                FifoMatchDB.open_trade_row_hash == match.open_trade_row_hash,
                FifoMatchDB.close_trade_row_hash == match.close_trade_row_hash,
                FifoMatchDB.volume == match.volume,
            ).first()
            if exists:
                continue
            session.add(FifoMatchDB(**_dump_model(match)))
            counters["inserted_fifo_matches"] += 1

        for lot in result.get("position_lots", []):
            exists = session.query(PositionLotDB).filter(
                PositionLotDB.trade_date == lot.trade_date,
                PositionLotDB.account_id == lot.account_id,
                PositionLotDB.instrument_code == lot.instrument_code,
                PositionLotDB.direction == lot.direction,
                PositionLotDB.source_file == lot.source_file,
                PositionLotDB.open_trade_row_hash == lot.open_trade_row_hash,
            ).first()
            if exists:
                continue
            session.add(PositionLotDB(**_dump_model(lot)))
            counters["inserted_position_lots"] += 1

        for acc in result.get("accounts", []):
            exists = session.query(AccountDailySnapshotDB).filter(
                AccountDailySnapshotDB.trade_date == acc.trade_date,
                AccountDailySnapshotDB.account_id == acc.account_id,
                AccountDailySnapshotDB.source_file == acc.source_file,
            ).first()
            if exists:
                continue
            session.add(AccountDailySnapshotDB(**_dump_model(acc)))
            counters["inserted_accounts"] += 1

        for issue in result.get("validation_issues", []):
            session.add(ValidationIssueDB(**_dump_model(issue)))
            counters["inserted_validation_issues"] += 1

        session.commit()
        return counters

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def save_source_file_record(
    file_name: str,
    file_path: str,
    file_hash: str,
    parser_name: str,
    status: str,
    error_message: str | None = None,
):
    session = SessionLocal()

    try:
        db_obj = SourceFileDB(
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            parser_name=parser_name,
            status=status,
            error_message=error_message,
        )
        session.add(db_obj)
        session.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def is_file_already_processed(file_hash: str) -> bool:
    session = SessionLocal()

    try:
        exists = session.query(SourceFileDB).filter(
            SourceFileDB.file_hash == file_hash,
            SourceFileDB.status == "success",
        ).first()

        return exists is not None

    finally:
        session.close()


def create_chinese_query_views(engine):
    view_sql = [
        "CREATE VIEW IF NOT EXISTS 资金状况表 AS SELECT * FROM account_daily_snapshots",
        "CREATE VIEW IF NOT EXISTS 出入金流水表 AS SELECT * FROM cash_flows",
        "CREATE VIEW IF NOT EXISTS 行权明细表 AS SELECT * FROM option_exercise_details",
        "CREATE VIEW IF NOT EXISTS 持仓明细表 AS SELECT * FROM position_details",
        "CREATE VIEW IF NOT EXISTS 持仓汇总表 AS SELECT * FROM position_snapshots",
        "CREATE VIEW IF NOT EXISTS 成交汇总表 AS SELECT * FROM trade_summaries",
    ]

    with engine.begin() as connection:
        for sql in view_sql:
            connection.execute(text(sql))
