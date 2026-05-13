import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
INBOX_DIR = DATA_DIR / "inbox"
ARCHIVE_DIR = DATA_DIR / "archive"
ERROR_DIR = DATA_DIR / "error"

DB_DIR = BASE_DIR / "db"
SETTLEMENT_DB_PATH = Path(
    os.getenv("SETTLEMENT_DB_PATH", str(DB_DIR / "trading.db"))
).expanduser()
DB_PATH = SETTLEMENT_DB_PATH

MARKET_DB_PATH = Path(
    os.getenv(
        "MARKET_DB_PATH",
        r"D:\CodeProjects\futures_exchange_daily_data\data\futures_daily.sqlite",
    )
).expanduser()
MARKET_SETTLEMENT_QUERY = os.getenv(
    "MARKET_SETTLEMENT_QUERY",
    """
    SELECT settlement_price
    FROM futures_daily
    WHERE trade_date = :trade_date
      AND instrument_code = :instrument_code
    LIMIT 1
    """.strip(),
)

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"

def ensure_directories():
    DATA_DIR.mkdir(exist_ok=True)
    INBOX_DIR.mkdir(exist_ok=True)
    ARCHIVE_DIR.mkdir(exist_ok=True)
    ERROR_DIR.mkdir(exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
