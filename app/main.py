import re

from app.config import ARCHIVE_DIR, ERROR_DIR, INBOX_DIR, ensure_directories
from app.db.base import engine
from app.db.models import Base
from app.db_writer import (
    BlockingValidationError,
    create_chinese_query_views,
    is_file_already_processed,
    save_source_file_record,
    save_to_db,
)
from app.parsers.registry import ParserRegistry
from app.utils.file_hash import calculate_file_md5
from app.utils.file_move import move_to_archive, move_to_error
from app.utils.logger import setup_logger


def file_sort_key(file_path):
    match = re.search(r"(\d+).*?(\d{4})-(\d{2})-(\d{2})", file_path.name)
    if not match:
        return "", "99999999", file_path.name
    account, year, month, day = match.groups()
    return account, f"{year}{month}{day}", file_path.name


def main():
    print(">>> 程序已启动 <<<")

    ensure_directories()
    Base.metadata.create_all(bind=engine)
    create_chinese_query_views(engine)

    logger = setup_logger()
    logger.info("程序启动成功")
    logger.info("收件目录: %s", INBOX_DIR)

    files = sorted(
        [
            f for f in list(INBOX_DIR.glob("*"))
            if f.is_file() and not f.name.startswith("~$")
        ],
        key=file_sort_key,
    )
    logger.info("发现文件数量: %s", len(files))

    registry = ParserRegistry()

    for file in files:
        logger.info("待处理文件: %s", file.name)
        parser = None
        file_hash = None

        try:
            file_hash = calculate_file_md5(file)
            if is_file_already_processed(file_hash):
                logger.info("跳过已成功处理文件: %s", file.name)
                try:
                    archived_path = move_to_archive(file, ARCHIVE_DIR)
                    logger.info("已处理文件已归档: %s", archived_path)
                except PermissionError as e:
                    logger.warning("已处理文件归档失败，可能正被占用: %s, 错误: %s", file.name, e)
                continue

            parser = registry.get_parser(file)
            if not parser:
                logger.warning("未找到可用解析器: %s", file.name)
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
                    logger.info("文件已移入错误目录: %s", error_path)
                except PermissionError as e:
                    logger.warning("未识别文件移动到错误目录失败，可能正被占用: %s, 错误: %s", file.name, e)
                continue

            logger.info("使用解析器: %s", parser.name)
            result = parser.parse(file)
            logger.info(
                "解析完成: %s | account=%s deposit=%s transaction=%s closed=%s pos_detail=%s positions=%s exercise=%s",
                file.name,
                len(result.get("account_summary", [])),
                len(result.get("deposit_withdrawal", [])),
                len(result.get("transaction_record", [])),
                len(result.get("position_closed", [])),
                len(result.get("positions_detail", [])),
                len(result.get("positions", [])),
                len(result.get("exercise_statement", [])),
            )

            save_result = save_to_db(result)
            save_source_file_record(
                file_name=file.name,
                file_path=str(file),
                file_hash=file_hash,
                parser_name=parser.name,
                status="success",
            )

            logger.info("数据已写入数据库: %s", file.name)
            logger.info("本次新增: %s", save_result)

            try:
                archived_path = move_to_archive(file, ARCHIVE_DIR)
                logger.info("文件已归档: %s", archived_path)
            except PermissionError as e:
                logger.warning("文件处理成功，但归档失败，可能正被占用: %s, 错误: %s", file.name, e)

        except BlockingValidationError as e:
            logger.error("关键校验失败，业务数据未入库: %s, 错误: %s", file.name, e)
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
                logger.info("文件已移入错误目录: %s", error_path)
            except PermissionError as pe:
                logger.warning("文件处理失败，且移动到错误目录时被占用: %s, 错误: %s", file.name, pe)

        except Exception as e:
            logger.exception("解析失败: %s, 错误: %s", file.name, e)
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
                logger.info("文件已移入错误目录: %s", error_path)
            except PermissionError as pe:
                logger.warning("文件处理失败，且移动到错误目录时被占用: %s, 错误: %s", file.name, pe)


if __name__ == "__main__":
    main()
