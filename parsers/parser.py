import abc
from collections import Counter
from typing import List, Tuple
import numpy as np
from pdfminer.layout import LTFigure, LTLine, LTChar, LTPage, LTTextLineHorizontal

from utils.utils import Heading


class Parser:

    def __init__(self, cols: int, is_uppercase_title=True):
        self.cols = cols
        self.is_uppercasee_title = is_uppercase_title

    @abc.abstractmethod
    def check_limits(self, line: LTTextLineHorizontal, page_index: int = 0, column: int = 0) -> bool:
        pass

    @abc.abstractmethod
    def check_heading(self, line: LTTextLineHorizontal, heading_list: List[Heading] = None) -> bool:
        pass

    def is_horizontal(self, line: LTTextLineHorizontal) -> bool:
        chars = [char for char in line if isinstance(char, LTChar)]
        return sum(int(char.upright) for char in chars) / len(chars) >= 0.5

    def check_page(self, page: LTPage) -> bool:
        return page.width < page.height
    
    def exclude_tables_and_footnotes(self, lines: List[LTTextLineHorizontal], page: LTPage, column: int) -> List[LTTextLineHorizontal]:
        return lines

    def exclude_shapes(self, lines: List[LTTextLineHorizontal], page: LTPage, column: int) -> List[LTTextLineHorizontal]:
        figures = [
            obj 
            for obj in page 
            if isinstance(obj, LTFigure) and self.check_limits(obj, page.pageid - 1, column)
        ]
        return [
            line
            for line in lines
            if all(line.y0 > fig.y1 or line.y1 < fig.y0 or line.x0 > fig.x1 or line.x1 < fig.x0 for fig in figures)
        ]
        
    def get_size(self, line: LTTextLineHorizontal) -> float:
        return np.mean([char.height for char in line if isinstance(char, LTChar)])
    
    def get_font(self, line: LTTextLineHorizontal) -> str:
        return Counter([char.fontname for char in line if isinstance(char, LTChar)]).most_common(1)[0][0].lower()
    
    def greyscale(self, line: LTTextLineHorizontal) -> bool:
        colors = np.mean([char.graphicstate.ncolor or 0. for char in line if isinstance(char, LTChar)], axis=0)
        if colors.shape:
            return sum(colors[:2]) < 0.1
        return True

    @abc.abstractmethod
    def heading_level(self, line: LTTextLineHorizontal) -> int:  
        pass

    def check_heading_list(self, line: LTTextLineHorizontal, heading_list: List[Heading]) -> Heading:
        line = line.get_text()
        if heading_list:
            for heading in heading_list:
                if line.get_text() in heading.title:
                    return heading
                for subheading in heading.subheadings:
                    if line.get_text() in subheading.title:
                        return heading
        return None
