from pydantic import BaseModel


class ValidationResult(BaseModel):
    check_name: str = ""
    status: str = ""
    actual_value: str | None = None
    expected_value: str | None = None
    diff_value: str | None = None
    tolerance: str | None = None
    details: str | None = None
    source_file: str = ""
    date: str | None = None
    account_id: str | None = None
    is_blocking: bool = False


ValidationIssue = ValidationResult
