import re
from typing import List

from pdfminer.layout import (LTFigure, LTImage, LTLine, LTPage,
                             LTTextBoxHorizontal, LTTextLine,
                             LTTextLineHorizontal)

from parsers.parser import Parser

heading_pattern = re.compile(r"^([0-9]+(\.)?)+\s*")

class Paragraph:
    SAME_PARAGRAPH = re.compile(r"[^.!?\s]\s*\n$")
    LINE_ENDING = re.compile(r"\S(-|~)\s*\n$")

    def __init__(self, text: str):
        self.buffer = list(text)
        self.add_space()
        # if not self.remove_hyphen():
        #     self.add_space()

    def pop(self, k=1):
        while k > 0:
            self.buffer.pop()
            k -= 1

    def endswith(self, char: str):
        return self.buffer[-1] == char

    def add_space(self):
        if self.buffer[-1] == "\n" and self.buffer[-2] != " ":
            self.buffer.insert(-1, " ")

    def remove_hyphen(self):
        hyphen = re.search(self.LINE_ENDING, "".join(self.buffer[-5:]))
        if hyphen:
            a, b = hyphen.span()  # TODO: "opportunities for pro-"
            self.pop(b - a - 1)
        return hyphen

    def same_paragraph(self, next_line: str):
        return next_line[0].islower() or re.search(self.SAME_PARAGRAPH, "".join(self.buffer[-5:]))
        # TODO: [35] -> splits in 2 paragraphs

    def get_text(self):
        return "".join(self.buffer)

    def __str__(self):
        return self.get_text()

    def __repr__(self):
        return self.get_text()

    def append(self, text: str):
        self.buffer += list(text)
        self.add_space()
        # if not self.remove_hyphen():
        #     self.add_space()

    def to_html(self):
        return f"<p>{self.get_text().strip()}</p>"


class Section:

    def __init__(self, heading: LTLine, level=0):
        self.heading = heading.get_text().strip()
        self.level = level
        match = re.match(heading_pattern, self.heading)
        if match:
            self.heading_index = match.group(0).strip()
        else:
            self.heading_index = None
        self.subsections: List[Section] = []
        self.paragraphs: List[Paragraph] = []

    def last_section(self) -> "Section":
        if self.subsections:
            return self.subsections[-1]
        return self

    def last_paragraph(self) -> Paragraph:
        if self.subsections:
            return self.subsections[-1].last_paragraph()
        return self.paragraphs[-1] if self.paragraphs else None

    def append_paragraph(self, paragraph: Paragraph):
        if self.subsections:
            self.subsections[-1].append_paragraph(paragraph)
        else:
            self.paragraphs.append(paragraph)

    def add_heading(self, line: LTLine, level: int) -> bool:
        if level == self.level:
            if self.last_paragraph():
                return False
            else:
                self.last_section().heading += " " + line.get_text().strip()
                return True
        if not self.subsections or not self.subsections[-1].add_heading(line, level):
            self.subsections.append(Section(line, level))
        return True    
        
    def __str__(self):
        return self.heading

    def __repr__(self):
        return self.heading

    def empty(self):
        return not self.subsections and not self.paragraphs
 
    def remove_empty(self):
        if sum(len(par.get_text()) for par in self.paragraphs) < 50:
            self.paragraphs = []
        for section in self.subsections:
            section.remove_empty()
        self.subsections = [section for section in self.subsections if not section.empty()]
