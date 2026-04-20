import hashlib
from pathlib import Path


def calculate_file_md5(file_path: Path) -> str:
    md5 = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)

    return md5.hexdigest()