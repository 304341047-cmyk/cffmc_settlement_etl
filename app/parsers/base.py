from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseParser(ABC):
    name: str = "BaseParser"

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> dict[str, Any]:
        pass

    def parse_result_template(self) -> dict[str, Any]:
        return {
            "account_summary": [],
            "deposit_withdrawal": [],
            "transaction_record": [],
            "exercise_statement": [],
            "position_closed": [],
            "positions_detail": [],
            "positions": [],
            "fifo_matches": [],
            "position_lots": [],
            "fifo_positions": [],
            "validation_result": [],
            "warnings": [],
        }
