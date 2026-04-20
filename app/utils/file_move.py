from pathlib import Path
import shutil
from datetime import datetime


def move_to_archive(file_path: Path, archive_root: Path) -> Path:
    """
    成功处理后移动到 archive/yyyy-mm/
    """
    month_folder = datetime.now().strftime("%Y-%m")
    target_dir = archive_root / month_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / file_path.name
    shutil.move(str(file_path), str(target_path))
    return target_path


def move_to_error(file_path: Path, error_root: Path) -> Path:
    """
    失败处理后移动到 error/
    """
    error_root.mkdir(parents=True, exist_ok=True)

    target_path = error_root / file_path.name
    shutil.move(str(file_path), str(target_path))
    return target_path