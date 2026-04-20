from pathlib import Path
from typing import List, Optional

from app.parsers.base import BaseParser
from app.parsers.dummy_parser import DummyParser
from app.parsers.cffmc_settlement_parser import CFFMCSettlementParser


class ParserRegistry:
    def __init__(self):
        # 顺序很重要：先匹配真实解析器，再匹配Dummy
        self.parsers: List[BaseParser] = [
            CFFMCSettlementParser(),
            DummyParser(),
        ]

    def get_parser(self, file_path: Path) -> Optional[BaseParser]:
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None