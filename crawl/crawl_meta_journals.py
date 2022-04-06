import math
import time

import requests
from bs4 import BeautifulSoup
import json
import traceback
from pathlib import Path

import utils.utils as utils


def get_elsevier_volumes(link):
    response_book = requests.get(link)
    soup_book = BeautifulSoup(response_book.text, 'html.parser')
    pages = soup_book.find(class_="pagination-pages-label")
    if pages:
        pages = pages.text


def elsevier(link):
    get_elsevier_volumes(link)


def springer(link, name, number):
    response_book = requests.get(link)
    soup_book = BeautifulSoup(response_book.text, 'html.parser')
    volumes = soup_book.select('a[href^="/journal/'+str(number)+'/volumes-and-issues"]')

    result = []

    for volume in volumes:
        volume_href = 'https://link.springer.com/' + volume["href"]
        response_volume = requests.get(volume_href)
        soup_volume = BeautifulSoup(response_volume.text, 'html.parser')
        articles = soup_volume.select('a[href^="https://link.springer.com/article/"]')
        for article in articles:
            article_href = article["href"]

            print(article_href)

            response_article = requests.get(article_href)
            soup_article = BeautifulSoup(response_article.text, 'html.parser')

            journal_id = utils.get_meta_info(soup_article, "journal_id")
            journal_name = utils.get_meta_info(soup_article, "prism.publicationName")
            type = utils.get_meta_info(soup_article, "dc.type")
            journal_volume = utils.get_meta_info(soup_article, "citation_volume")
            number = utils.get_meta_info(soup_article, "citation_issue")
            section = utils.get_meta_info(soup_article, "prism.section")
            citation_publisher = utils.get_meta_info(soup_article, "citation_publisher")
            citation_title = utils.get_meta_info(soup_article, "citation_title")
            citation_doi = utils.get_meta_info(soup_article, "citation_doi")
            citation_language = utils.get_meta_info(soup_article, "citation_language")
            citation_fulltext_html_url = utils.get_meta_info(soup_article, "citation_fulltext_html_url")
            citation_pdf_url = utils.get_meta_info(soup_article, "citation_pdf_url")
            citation_springer_api_url = utils.get_meta_info(soup_article, "citation_springer_api_url")
            citation_firstpage = utils.get_meta_info(soup_article, "citation_firstpage")
            citation_lastpage = utils.get_meta_info(soup_article, "citation_lastpage")
            authors = utils.get_meta_info_list(soup_article, "citation_author")
            institutions = utils.get_meta_info_list(soup_article, "citation_author_institution")
            emails = utils.get_meta_info_list(soup_article, "citation_author_email")
            keywords = utils.get_itemprop_info_list(soup_article, "span", "about")
            abstract = utils.get_meta_info(soup_article, "dc.description")
            citation_publication_date = utils.get_meta_info(soup_article, "citation_publication_date")

            # check download link
            download_link = soup_article.find(class_="c-pdf-download__link")
            if download_link:
                link = download_link["href"]
                if link:
                    utils.download_pdf(link, 'springer/' + name, citation_doi)

            result.append({
                'journal_id': journal_id,
                'journal_name': journal_name,
                'type': type,
                'volume': journal_volume,
                'number': number,
                'section': section,
                'publisher': citation_publisher,
                'title': citation_title,
                'doi': citation_doi,
                'language': citation_language,
                'full_text': citation_fulltext_html_url,
                'pdf_url': citation_pdf_url,
                'spring_api_url': citation_springer_api_url,
                'start_page': citation_firstpage,
                'last_page': citation_lastpage,
                'authors': authors,
                'institutions': institutions,
                'correspond_email': emails,
                'keywords': keywords,
                'abstract': abstract,
                'date': citation_publication_date})
    return result


def elsevier_json():
    links = [
        "https://www.sciencedirect.com/journal/computers-and-education/",
        "https://www.sciencedirect.com/journal/computers-in-human-behavior/",
        "https://www.sciencedirect.com/journal/assessing-writing/"
    ]

    for link in links:
        print(link)
        result = elsevier(link + "issues")

        # with open(conf + '1.json', 'w', encoding='UTF8') as f:
        #     json.dump(result, f)
        #     print('done')


def springer_json():
    links = [
        # {
        #   "name": "ijCSCL",
        #   "link": "https://link.springer.com/journal/11412/volumes-and-issues",
        #   "number": 11412
        #
        #  },
        {
            "name": "BRM",
             "link": "https://link.springer.com/journal/13428/volumes-and-issues",
             "number": 13428
         }
    ]

    for link in links:
        print(link["link"])
        result = springer(link["link"], link["name"], link["number"])
        with open('./pdfs/springer/' + link["name"] + '/meta.json', 'w', encoding='UTF8') as f:
            json.dump(result, f)
            print('done')


def frontiers(link, index):
    # params from Chrome :)
    headers_dict = {
        'Connection': 'keep-alive',
        'sec-ch-ua': '"Google Chrome";v="93", " Not;A Brand";v="99", "Chromium";v="93"',
        'X-NewRelic-ID': 'VgUHUl5WGwAAVFZaDwY=',
        'sec-ch-ua-mobile': '?0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': '*/*',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua-platform': '"Windows"',
        'Origin': 'https://www.frontiersin.org',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'https://www.frontiersin.org/journals/psychology',
        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8,ro;q=0.7,ca;q=0.6',
        'Cookie': 'ajs_anonymous_id=f32486de-bdd1-418b-bb9a-98c5eb345be6; _ga=GA1.2.178866417.1628436330; CurrentSessionId=80b3a8f9-2f37-4854-973c-98a5be01be19; __atuvc=2%7C32%2C0%7C33%2C0%7C34%2C1%7C35; __atssc=google%3B2; OptanonAlertBoxClosed=2021-10-05T19:17:12.855Z; OptanonConsent=isGpcEnabled=0&datestamp=Tue+Oct+05+2021+22%3A17%3A12+GMT%2B0300+(Eastern+European+Summer+Time)&version=6.19.0&isIABGlobal=false&hosts=&consentId=2c6f26ee-a20b-4cbc-bbfc-51db8dc2599b&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1; _gid=GA1.2.1625557949.1633461433',
    }

    data = {
        "JournalId": 36,
        "SectionId": 0,
        "SortType": "recentdate"
    }

    response = requests.post("https://www.frontiersin.org/api/journals/article/filter?index=" + str(index), data=data,
                             headers=headers_dict)
    if response:
        article_json = response.json()
        articles = article_json["ArticleCollection"]["Articles"]
        count = article_json["Count"]
        return translate_frontier_meta(articles)


def translate_frontier_meta(data):
    result = []

    if data is None:
        return result

    for meta in data:
        print(meta["Url"])
        response_book = requests.get(meta["Url"])
        soup_book = BeautifulSoup(response_book.text, 'html.parser')

        entry = {
            'journal_name': utils.get_meta_info(soup_book, "citation_journal_title"),
            'type': meta["ArticleType"],
            'volume': utils.get_meta_info(soup_book, "citation_volume"),
            'publisher': utils.get_meta_info(soup_book, "citation_publisher"),
            'title': meta["Title"],
            'doi': meta["DoiUrl"],
            'language': utils.get_meta_info(soup_book, "citation_language"),
            'pages': utils.get_meta_info(soup_book, "citation_pages"),
            'authors': utils.get_meta_info_list(soup_book, "citation_author"),
            'institutions': utils.get_meta_info_list(soup_book, "citation_author_institution"),
            'correspond_email': utils.get_meta_info_list(soup_book, "citation_author_email"),
            'keywords': utils.get_meta_info(soup_book, "citation_keywords"),
            'abstract': meta["Abstract"],
            'date': utils.get_meta_info(soup_book, "citation_date"),
            'online_date': utils.get_meta_info(soup_book, "citation_online_date"),
            'url': meta["Url"]}

        # try to download PDF
        doi = meta["DOI"].split("/")[-1]
        url = meta["Url"].replace("/abstract", "")
        utils.download_pdf(url + "/pdf", "/frontiers/" + str(entry["date"]), doi)

        result.append(entry)

    return result


def frontiers_json():
    links = [
        "https://www.frontiersin.org/journals/psychology"
    ]

    for link in links:
        print(link)
        result = []
        for i in range(math.ceil(25257/20)):
            print("index: " + str(i))
            result.extend(frontiers(link, i))
        with open('./frontiers/meta.json', 'w', encoding='UTF8') as f:
            json.dump(result, f)
            print('done')


# elsevier_json()
# springer_json()
frontiers_json()