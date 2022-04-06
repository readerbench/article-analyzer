from collections import Counter

from typing import List
import numpy as np
from pdfminer.layout import LTLine, LTChar, LTPage, LTTextLineHorizontal

from parsers.parser import Parser
from utils.utils import Heading


class LakSigcseParser(Parser):

    def __init__(self):
        super().__init__(2, False)

    def check_limits(self, line: LTTextLineHorizontal, page_index: int = 0, column: int = 0) -> bool:
        if line.y0 < 60 or line.y1 > 720:
            return False

        if page_index == 0:
            if column == 0 and line.x1 > 300:
                return False
            if column == 1 and line.x0 < 300:
                return False

        # check font size
        avg_size = self.get_size(line)
        if avg_size < 8:
            return False

        if column == 0:
            return line.x0 < 295
        else:
            return line.x1 > 300

    def check_heading(self, line: LTTextLineHorizontal, heading_list: List[Heading] = None) -> bool:
        fonts = Counter([char.fontname for char in line if isinstance(char, LTChar)])
        font = fonts.most_common()[0][0].lower()
        potential_subheading = 'cmbx' in font or "bold" in font or ".b" in font \
                               or 'nimbusromno9l-medi' in font or 'libertinetb' in font or \
                               'libertineb' in font

        avg_size = self.get_size(line)

        # if line.x0 > 100:  # too in the middle
        #     return False

        if 10.5 < avg_size < 13:
            potential_subheading = potential_subheading and True

        if potential_subheading:
            if "." in line.get_text() and avg_size > 10:
                return True
        return False

    def exclude_tables_and_footnotes(self, lines: List[LTTextLineHorizontal], page: LTPage, column=0) -> List[LTTextLineHorizontal]:
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
