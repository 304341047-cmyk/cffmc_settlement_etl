from datetime import date

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    trade_date: date | None = None
    account_id: str | None = None
    source_file: str | None = None
    check_name: str
    severity: str = "error"
    message: str
    expected_value: str | None = None
    actual_value: str | None = None
    is_blocking: bool = True
