from app.db.base import SessionLocal
from app.db.models import (
    TradeExecutionDB,
    PositionDetailDB,
    PositionSnapshotDB,
    AccountDailySnapshotDB,
    SourceFileDB,
    OptionExerciseDetailDB,
)


def save_to_db(result: dict):
    session = SessionLocal()

    inserted_trades = 0
    inserted_position_details = 0
    inserted_positions = 0
    inserted_accounts = 0
    inserted_exercise_details = 0

    try:
        # ===== 成交 =====
        for trade in result.get("trades", []):
            exists = session.query(TradeExecutionDB).filter(
                TradeExecutionDB.account_id == trade.account_id,
                TradeExecutionDB.trade_date == trade.trade_date,
                TradeExecutionDB.trade_no == trade.trade_no,
            ).first()

            if exists:
                continue

            db_obj = TradeExecutionDB(**trade.model_dump())
            session.add(db_obj)
            inserted_trades += 1

        # ===== 持仓明细 =====
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

            db_obj = PositionDetailDB(**pos.model_dump())
            session.add(db_obj)
            inserted_position_details += 1

        # ===== 持仓快照 =====
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

            db_obj = PositionSnapshotDB(**pos.model_dump())
            session.add(db_obj)
            inserted_positions += 1

        # ===== 行权明细 =====
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

            db_obj = OptionExerciseDetailDB(**ex.model_dump())
            session.add(db_obj)
            inserted_exercise_details += 1

        # ===== 账户 =====
        for acc in result.get("accounts", []):
            exists = session.query(AccountDailySnapshotDB).filter(
                AccountDailySnapshotDB.trade_date == acc.trade_date,
                AccountDailySnapshotDB.account_id == acc.account_id,
                AccountDailySnapshotDB.source_file == acc.source_file,
            ).first()

            if exists:
                continue

            db_obj = AccountDailySnapshotDB(**acc.model_dump())
            session.add(db_obj)
            inserted_accounts += 1

        session.commit()

        return {
            "inserted_trades": inserted_trades,
            "inserted_position_details": inserted_position_details,
            "inserted_positions": inserted_positions,
            "inserted_accounts": inserted_accounts,
            "inserted_exercise_details": inserted_exercise_details,
        }

    except Exception as e:
        session.rollback()
        raise e

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