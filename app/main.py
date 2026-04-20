from app.config import ensure_directories, INBOX_DIR, ARCHIVE_DIR, ERROR_DIR
from app.utils.file_move import move_to_archive, move_to_error
from app.utils.logger import setup_logger
from app.parsers.registry import ParserRegistry

from app.db.base import engine
from app.db.models import Base
from app.db_writer import (
    save_to_db,
    save_source_file_record,
    is_file_already_processed,
)
from app.utils.file_hash import calculate_file_md5


def main():
    print(">>> 程序已启动 <<<")

    ensure_directories()
    Base.metadata.create_all(bind=engine)

    logger = setup_logger()
    logger.info("程序启动成功")
    logger.info(f"收件目录: {INBOX_DIR}")

    # 先冻结文件列表，避免循环过程中移动文件带来干扰
    files = [
        f for f in list(INBOX_DIR.glob("*"))
        if f.is_file() and not f.name.startswith("~$")
    ]

    logger.info(f"发现文件数量: {len(files)}")

    registry = ParserRegistry()

    for file in files:
        logger.info(f"待处理文件: {file.name}")

        parser = None
        file_hash = None

        try:
            # 1. 先算 hash
            file_hash = calculate_file_md5(file)

            # 2. 文件级去重：已成功处理过则直接跳过并归档
            if is_file_already_processed(file_hash):
                logger.info(f"跳过已处理文件: {file.name}")
                try:
                    archived_path = move_to_archive(file, ARCHIVE_DIR)
                    logger.info(f"已处理文件已归档: {archived_path}")
                except PermissionError as e:
                    logger.warning(f"已处理文件归档失败，可能正被占用: {file.name}, 错误: {e}")
                continue

            # 3. 查找解析器
            parser = registry.get_parser(file)
            if not parser:
                logger.warning(f"未找到可用解析器: {file.name}")

                save_source_file_record(
                    file_name=file.name,
                    file_path=str(file),
                    file_hash=file_hash,
                    parser_name=None,
                    status="failed",
                    error_message="未找到可用解析器",
                )

                try:
                    error_path = move_to_error(file, ERROR_DIR)
                    logger.info(f"文件已移入错误目录: {error_path}")
                except PermissionError as e:
                    logger.warning(f"未识别文件移动到错误目录失败，可能正被占用: {file.name}, 错误: {e}")
                continue

            logger.info(f"使用解析器: {parser.name}")

            # 4. 解析
            result = parser.parse(file)

            logger.info(f"解析完成: {file.name}")
            logger.info(f"成交记录数: {len(result.get('trades', []))}")
            logger.info(f"持仓明细数: {len(result.get('position_details', []))}")
            logger.info(f"持仓快照数: {len(result.get('positions', []))}")
            logger.info(f"账户快照数: {len(result.get('accounts', []))}")
            logger.info(f"行权明细数: {len(result.get('exercise_details', []))}")

            validation = result.get("validation", {})
            commission_check = validation.get("commission_check", {})
            if commission_check:
                c = commission_check
                logger.info(
                    f"手续费校验 -> "
                    f"期货: {c['futures']}, "
                    f"期权: {c['option']}, "
                    f"行权: {c['exercise']}, "
                    f"合计: {c['total_calc']}, "
                    f"日报: {c['account']}, "
                    f"差额: {c['diff']}, "
                    f"是否匹配: {c['is_match']}"
                )

            # 5. 入库
            save_result = save_to_db(result)

            # 6. 记录来源文件
            save_source_file_record(
                file_name=file.name,
                file_path=str(file),
                file_hash=file_hash,
                parser_name=parser.name,
                status="success",
            )

            logger.info(f"数据已写入数据库: {file.name}")
            logger.info(
                f"本次新增 -> "
                f"成交: {save_result.get('inserted_trades', 0)}, "
                f"持仓明细: {save_result.get('inserted_position_details', 0)}, "
                f"持仓快照: {save_result.get('inserted_positions', 0)}, "
                f"账户: {save_result.get('inserted_accounts', 0)}"
            )

            # 7. 成功后归档
            try:
                archived_path = move_to_archive(file, ARCHIVE_DIR)
                logger.info(f"文件已归档: {archived_path}")
            except PermissionError as e:
                logger.warning(f"文件处理成功，但归档失败，可能正被占用: {file.name}, 错误: {e}")

        except Exception as e:
            logger.exception(f"解析失败: {file.name}, 错误: {e}")

            save_source_file_record(
                file_name=file.name,
                file_path=str(file),
                file_hash=file_hash or "",
                parser_name=parser.name if parser else None,
                status="failed",
                error_message=str(e),
            )

            try:
                error_path = move_to_error(file, ERROR_DIR)
                logger.info(f"文件已移入错误目录: {error_path}")
            except PermissionError as pe:
                logger.warning(f"文件处理失败，且移动到错误目录时被占用: {file.name}, 错误: {pe}")


if __name__ == "__main__":
    main()