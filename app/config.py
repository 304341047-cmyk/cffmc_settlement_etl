from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = DATA_DIR / "inbox"
ARCHIVE_DIR = DATA_DIR / "archive"
ERROR_DIR = DATA_DIR / "error"

DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "trading.db"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

def ensure_directories():
    DATA_DIR.mkdir(exist_ok=True)
    INBOX_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    ERROR_DIR.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)