from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any


class BaseParser(ABC):
    name: str = "BaseParser"

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> Dict[str, Any]:
        pass

    def parse_result_template(self) -> Dict[str, Any]:
        return {
            "trades": [],
            "cash_flows": [],
            "trade_summaries": [],
            "close_details": [],
            "positions": [],
            "position_details": [],
            "accounts": [],
            "exercise_details": [],
            "fifo_matches": [],
            "position_lots": [],
            "validation_issues": [],
        }
