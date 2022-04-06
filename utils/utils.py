from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from elasticsearch.client import Elasticsearch

import requests
from bs4 import BeautifulSoup


class Heading:
    def __init__(self, title: str, parent_index: int, index: int, subheadings: List['Heading']):
        self.title = title
        self.parent_index = parent_index
        self.index = index
        self.subheadings = subheadings


def get_meta_info(soup, meta_name):
    info = soup.find("meta", attrs={'name': meta_name})
    info = info["content"] if info is not None else None
    return info


def get_meta_info_list(soup, meta_name):
    info = soup.find_all("meta", attrs={'name': meta_name})
    result = []
    for elem in info:
        result.append(elem["content"])
    return result


def get_itemprop_info_list(soup, html_elem, itemprop_name):
    info = soup.find_all(html_elem, itemprop=itemprop_name)
    result = []
    for elem in info:
        result.append(elem.text)
    return result


def download_pdf(link, path, doi):
    try:
        r = requests.get(link)
        Path("./pdfs/" + path).mkdir(parents=True, exist_ok=True)
        title = doi.replace("https://doi.dx.org/", "").replace("https://doi.org/", "").replace("/", "_")
        with open("./pdfs/" + path + "/" + title + ".pdf", 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print("Cannot download: " + link)
        print(e)


def clean_text(text: str) -> str:
    text = text \
        .replace("\xa0", " ") \
        .replace("’", "'") \
        .replace("“", '"') \
        .replace("”", '"') \
        .replace("``", '"') \
        .replace("''", '"')
    return BeautifulSoup(text, features="html.parser").get_text()


def get_year(article: Dict[str, Any]) -> int:
    return datetime.strptime(article["date"], "%Y/%m/%d").year


def get_filepath(article: Dict[str, Any]) -> str:
    try:
        return f"articles/{article['conf_abbr']}/{get_year(article)}/{article['doi'].split('/')[-1]}.pdf"
    except:
        return None


def simplify_doi(doi: str):
    return "/".join(doi.split("/")[-2:])


def get_entry_by_filename(filename: str, es: Elasticsearch):
    if filename.endswith(".pdf"):
        filename = filename[:-4]
    result = es.search(index="articles", query={"wildcard": {"doi": {"value": "*" + filename}}})
    return result["hits"]["hits"][0]
    result = result["hits"]["hits"]
    return result[0] if result else None

