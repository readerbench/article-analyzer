import re
from typing import List
import numpy as np
from pdfminer.layout import LTLine, LTChar, LTPage, LTTextLineHorizontal

from parsers.parser import Parser
from utils.utils import Heading


class FrontiersParser(Parser):
    
    BOLD = re.compile(f"\+univers-condensedbold$")
    ITALIC = re.compile(f"((\.|-)i)|(italic)$")

    def __init__(self, old_version=False):
        super().__init__(2)
        self.old_version = old_version

    def check_limits(self, line: LTTextLineHorizontal, page_index: int = 0, column: int = 0) -> bool:
        if line.y0 < 60 or line.y1 > 720:
            return False
        if page_index == 0 and not self.old_version:
            return column == 0 and line.x0 > 160
        if column == 0:
            return line.x0 < 295
        else:
            return line.x1 > 300

    def check_heading(self, line: LTTextLineHorizontal, heading_list: List[Heading] = None) -> bool:
        if self.old_version:
            font = self.get_font(line)
            return self.is_bold(line, font)
        else:
            avg_size = self.get_size(line)
            return 10.5 < avg_size < 13
    
    def is_bold(self, line: LTTextLineHorizontal, font: str = None) -> bool:
        if not font:
            font = self.get_font(line)
        return re.search(self.BOLD, font) != None

    def is_italic(self, line: LTTextLineHorizontal, font: str = None) -> bool:
        if not font:
            font = self.get_font(line)
        return re.search(self.ITALIC, font) != None

    def heading_level(self, line: LTTextLineHorizontal) -> int:
        if self.old_version:
            if self.greyscale(line):
                return 1
            else:
                return 0
        else:
            font = self.get_font(line)
            if line.get_text().isupper() or font.endswith("-bd"):
                return 0
            else:
                return 1

    def exclude_tables_and_footnotes(self, lines: List[LTTextLineHorizontal], page: LTPage, column = 0) -> List[LTTextLineHorizontal]:
        table_lines = [
            obj 
            for obj in page 
            if isinstance(obj, LTLine) and 
                round(obj.y0 * 10) == round(obj.y1 * 10) and
                self.check_limits(obj, page.pageid - 1, column)
        ]
        tables = {}
        for line in table_lines:
            limits = (round(line.x0 * 10), round(line.x1 * 10))
            if limits not in tables:
                tables[limits] = []
            tables[limits].append(line)
        footnotes = [
            table_lines[0].y0 
            for limits, table_lines in tables.items() 
            if len(table_lines) == 1 and table_lines[0].x1 - table_lines[0].x0 > 200]
        if len(footnotes) >= 1:
            min_y = min(footnotes)
        else:
            min_y = 60
        lines = [line for line in lines if line.y0 >= min_y]
        limits = [
            (min(table_lines, key=lambda x: x.y0).y0, max(table_lines, key=lambda x: x.y0).y0)
            for limits, table_lines in tables.items() if len(table_lines) > 1
        ]
        return [
            line
            for line in lines
            if all(line.y1 < a or line.y0 > b for a, b in limits)
        ]
