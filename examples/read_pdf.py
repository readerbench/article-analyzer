import os
import re
import traceback
from collections import Counter
from io import BytesIO, StringIO
from shutil import move
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, Dict, List, Tuple, Union
from elasticsearch.client import Elasticsearch

# import camelot
import numpy as np
import xmltodict
# from camelot.core import Table
from console_progressbar import ProgressBar
from pdfminer.high_level import extract_pages, extract_text, extract_text_to_fp
from pdfminer.layout import (LTFigure, LTImage, LTLine, LTPage,
                             LTTextBoxHorizontal, LTTextLine, LTTextLineHorizontal)
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfparser import PDFParser
from es_config import ES_HOSTNAME, ES_PASS, ES_PORT
from parsers.elsevier import ElsevierParser
from parsers.frontiers import FrontiersParser
from parsers.section import Paragraph, Section
from parsers.springer_conf import SpringerConfParser

from parsers.parser import Parser
from utils.utils import get_entry_by_filename, Heading

from PyPDF3 import PdfFileReader, PdfFileWriter
from PyPDF3.generic import Destination

YEAR_REGEX = [
    (re.compile(r"\[\]"), ""),
    (re.compile(r"--"), "00"),
    (re.compile(r"\d+-(\d+)"), "\1"),
    (re.compile(r"\D+"), ""),
]

heading_pattern = re.compile(r"^([0-9]+(\.)?)+\s*")

class LineWrapper:

    def __init__(self, line: LTTextLineHorizontal):
        self.inner = line

    def __lt__(self, other):
        if abs(self.inner.y0 - other.inner.y0) < 2:  # same line
            return self.inner.x0 < other.inner.x0
        return self.inner.y0 > other.inner.y0

def detect_page_limits(lines: List[LTTextLine]) -> Tuple[int, int]:
    c = Counter(round(line.x0 / 10) for line in lines)
    a, _ = c.most_common(1)[0]
    c = Counter(round(line.x1 / 10) for line in lines)
    b, _ = c.most_common(1)[0]
    return a * 10, b * 10


def is_centered(line: LTTextLine, left: int, right: int) -> bool:
    return abs(line.x0 - left) > 50 and abs(line.x1 - right) > 50


def enumerate_outlines(outlines: List[Union[Destination, List]], parent_index=None) -> List[Heading]:
    headings = []
    heading_index = 0
    for outline in outlines:
        if isinstance(outline, Destination):
            heading_index += 1
            headings.append(Heading(outline['/Title'], parent_index, heading_index, []))
        elif isinstance(outline, List):
            headings[-1].subheadings = enumerate_outlines(outline, heading_index)
    return headings


def get_pdf_outlines(pdf_name):
    with open(pdf_name, "rb") as f:
        pdf = PdfFileReader(f, strict=False)
        if len(pdf.outlines) == 0:
            return []
        outlines = enumerate_outlines(pdf.outlines[1:][0])
        return outlines


def extract_content(pdf_file: str, parser: Parser) -> List[Section]:
    # tables = extract_tables(pdf_file)
    pages = list(extract_pages(pdf_file))
    heading_list = get_pdf_outlines(pdf_file)
    last_line = None
    index = 0
    found_start = False
    result: List[Section] = []
    for i, page in enumerate(pages):
        if not parser.check_page(page):
            continue
        for col in range(parser.cols):
            same_page = False
            lines = list(sorted(
                (line
                 for obj in page
                 if isinstance(obj, LTTextBoxHorizontal)
                 for line in obj
                 if parser.is_horizontal(line) and parser.check_limits(line, i, col)),
                key=LineWrapper))
            if not found_start:
                for j, line in enumerate(lines):
                    if parser.check_heading(line) and parser.heading_level(line) == 0:  # section = None
                        result.append(Section(line))
                        found_start = True
                        break
                lines = lines[(j + 1):]
            else:
                lines = parser.exclude_tables_and_footnotes(lines, page, col)
                lines = parser.exclude_shapes(lines, page, col)

            if not lines:
                continue
            left, right = detect_page_limits(lines)
            # if is_centered(lines[0], left, right) and len(lines[0].get_text().strip()) < 5:
            #     lines = lines[1:]
            # if is_centered(lines[-1], left, right) and len(lines[-1].get_text().strip()) < 5:
            #     lines = lines[:-1]
            # footnotes = find_footnotes(lines)
            # if footnotes:
            #     print(f"page: {i}")
            for line in lines:
                line_text = line.get_text().lstrip()
                if not line_text:
                    continue
                if parser.check_heading(line):  # section = last_section()
                    level = parser.heading_level(line)
                    if not result[-1].add_heading(line, level):
                        result.append(Section(line))
                    continue
                if result[-1].last_paragraph() is None:
                    result[-1].append_paragraph(Paragraph(line_text))
                    last_line = line
                    same_page = True
                    continue
                # same line
                if same_page and line.y1 > last_line.y0 and line.x0 > last_line.x1 \
                        and result[-1].last_paragraph().endswith("\n"):
                    result[-1].last_paragraph().pop()

                if abs(last_line.x1 - right) < 50 and (same_page or last_line.y0 < 100):
                    # separated word
                    if not result[-1].last_paragraph().remove_hyphen():
                        if result[-1].last_paragraph().same_paragraph(line_text):
                            result[-1].last_paragraph().pop()
                if result[-1].last_paragraph().endswith("\n"):
                    index += 1
                    result[-1].append_paragraph(Paragraph(line_text))
                else:
                    result[-1].last_paragraph().append(line_text)
                last_line = line
                same_page = True
    for section in result:
        section.remove_empty()
    result = [section for section in result if not section.empty()]
    return result


def structure_section(section: Section, result: List[Dict], parent=None):
    index = len(result)
    obj = {
        "heading": re.sub(heading_pattern, "", section.heading),
        "index": index,
        "parent": parent,
        "text": "\n".join(str(par) for par in section.paragraphs)
    }
    result.append(obj)
    for subsection in section.subsections:
        structure_section(subsection, result, parent=index)


def update_sections(filename: str, es: Elasticsearch, sections: List[Section]):
    entry = get_entry_by_filename(filename, es)
    if not entry:
        print(f"Not found: {filename}")
        raise Exception("Article not found")
    result = []
    for section in sections:
        structure_section(section, result)
    # print([(section["heading"], section["index"]) for section in result])
    entry["_source"]["sections"] = result
    es.update(index="articles", id=entry["_id"], doc=entry["_source"])


if __name__ == "__main__":
    es = Elasticsearch(
        hosts=[ES_HOSTNAME],
        http_auth=('elastic', ES_PASS),
        scheme="https",
        port=ES_PORT,
    )
    conf_abbr = "frontiers"
    parser = FrontiersParser(old_version=False)
    errors = []
    for year in [2015]:
        folder = f"articles/{conf_abbr}/{year}"
        print(year)
        folder = f"articles/{conf_abbr}/{year}"
        empty_folder = f"articles/{conf_abbr}/{year}-empty"
        errors_folder = f"articles/{conf_abbr}/{year}-errors"
        files = [filename for filename in os.listdir(folder) if not filename.startswith(".")] 
        pb = ProgressBar(len(files))
        for filename in files:
            # if filename != "fpsyg.2011.00262.pdf":
            #     continue
            print(filename)
            # with open(os.path.join(folder, filename), "rb") as f:
            try:
                sections = extract_content(os.path.join(folder, filename), parser)
                if not sections:
                    os.makedirs(empty_folder, exist_ok=True)
                    os.rename(os.path.join(folder, filename), os.path.join(empty_folder, filename))
                else:
                    update_sections(filename, es, sections)
            except KeyboardInterrupt:
                exit()
            except:
                os.makedirs(errors_folder, exist_ok=True)
                os.rename(os.path.join(folder, filename), os.path.join(errors_folder, filename))
                errors.append(filename)
            pb.next()
    print(len(errors))
    print(errors)
