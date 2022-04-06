from collections import Counter, deque
import re
from typing import List
import numpy as np
from pdfminer.layout import LTCurve, LTLine, LTChar, LTPage, LTTextLineHorizontal

from parsers.parser import Parser
from utils.utils import Heading


class ElsevierParser(Parser):
    
    NUMBERING = re.compile(r"^\s*\d")
    BOLD = re.compile(f"((\.|-)b)|(bold)$")
    ITALIC = re.compile(f"((\.|-)i)|(italic)$")

    def __init__(self, num_columns=1):
        super().__init__(num_columns, False)

    def check_limits(self, line: LTTextLineHorizontal, page_index: int = 0, column: int = 0) -> bool:
        if page_index == 0 and line.y1 > 450:
            return False
        if self.cols == 2:
            if line.y0 < 55 or line.y1 > 730:
                return False
            if column == 0: 
                return 30 < line.x0 < 300
            else:
                return 300 < line.x0 < 510
        else:
            if line.y0 < 55 or line.y1 > 690:
                return False
            return 35 < line.x0 < 510
        
    def check_heading(self, line: LTTextLineHorizontal, heading_list: List[Heading] = None) -> bool:
        if not re.match(self.NUMBERING, line.get_text()):
            return False
        font = self.get_font(line)
        return self.is_bold(line, font) or self.is_italic(line, font)
    
    def is_bold(self, line: LTTextLineHorizontal, font: str = None) -> bool:
        if not font:
            font = self.get_font(line)
        return re.search(self.BOLD, font) != None

    def is_italic(self, line: LTTextLineHorizontal, font: str = None) -> bool:
        if not font:
            font = self.get_font(line)
        return re.search(self.ITALIC, font) != None

    def exclude_tables_and_footnotes(self, lines: List[LTTextLineHorizontal], page: LTPage, column = 0) -> List[LTTextLineHorizontal]:
        # get all horizontal lines
        table_lines = [
            obj 
            for obj in page 
            if isinstance(obj, (LTLine, LTCurve)) and 
                abs(obj.y0 - obj.y1) < 1 and
                self.check_limits(obj, page.pageid - 1, column)
        ]
        
        # merge overlapping lines
        hlines = {}
        for line in table_lines:
            y = round(line.y0 * 10)
            if y not in hlines:
                hlines[y] = []
            hlines[y].append((round(line.x0 * 10), round(line.x1 * 10)))
        hlines = {
            y: (min(a for a, b in limits), max(b for a, b in limits))
            for y, limits in hlines.items()
        }
        # hlines = [(y, hlines[y]) for y in sorted(hlines)]

        # get table headers
        headers = [line for line in lines if self.is_bold(line) and line.get_text().startswith("Table")]
        

        tables = {}
        for y, limits in hlines.items():
            if limits not in tables:
                tables[limits] = []
            tables[limits].append(y / 10)
        
        footnotes = [
            table_lines[0] 
            for limits, table_lines in tables.items() 
            if len(table_lines) == 1 and limits[1] - limits[0] > 200 and table_lines[0] < 200]
        
        q = deque([sorted(table_lines, reverse=True) for x_limits, table_lines in tables.items() if len(table_lines) > 1])
        tables = []
        while len(q) > 0:
            table_lines = q.popleft()
            found = None
            for header in headers:
                if table_lines[-1] < header.y0 < table_lines[0]:
                    for i, y in enumerate(table_lines):
                        if y < header.y0:
                            tables.append((table_lines[i-1], header.y1))
                            q.append(table_lines[i:])
                            break
                    break
                elif table_lines[0] < header.y0 < table_lines[0] + 50:
                    found = header
            else:
                if found:
                    tables.append((table_lines[-1], found.y1))
                else:
                    tables.append((table_lines[-1], table_lines[0]))         
        if len(footnotes) >= 1:
            min_y = min(footnotes)
        else:
            min_y = 60
        lines = [line for line in lines if line.y0 >= min_y]


        return [
            line
            for line in lines
            if all(line.y1 < a or line.y0 > b for a, b in tables)
        ]
