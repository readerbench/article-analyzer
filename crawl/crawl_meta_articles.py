import time

import requests
from bs4 import BeautifulSoup
import json
import traceback
from pathlib import Path

import utils.utils as utils

def get_isls_article_links(parent_href):
    response_book = requests.get("https://repository.isls.org/" + parent_href)
    soup_book = BeautifulSoup(response_book.text, 'html.parser')
    chapters = soup_book.select('a[href^="/handle"]')

    articles = []
    new_book = None

    for chapter in chapters:
        href = chapter["href"]
        if parent_href not in href and "123456789" not in href\
                and "author" not in href and "statistics" not in href \
                and "offset" not in href and "simple-search" not in href:
            articles.append(href)
        if chapter.text.startswith("next") and "offset" in href:
            new_book = href

    return articles, new_book




def isls(link):
    result = []
    response = requests.get(link)
    html_soup = BeautifulSoup(response.text, 'html.parser')
    books = html_soup.select('a[href^="/handle"]')
    books = books[13::]  # ignore first book Rapid Community Report Series
    for book in books:
        citation_conference_title = book.text
        print(book.text)
        if citation_conference_title in ["ICLS 2020", "CSCL 2019", "ICLS 2018", "CSCL 2017",
                                         "ICLS 2016", "CSCL 2015", "ICLS 2014", "CSCL 2013",
                                         "ICLS 2012", "CSCL 2011", "ICLS 2010", "CSCL 2009",
                                         "ICLS 2008", "CSCL 2007"]:
            continue

        print("book: " + book['href'])

        articles = []
        new_book = book['href']

        while new_book:  # while there is a next button
            new_articles, new_book = get_isls_article_links(new_book)
            articles.extend(new_articles)

        for article in articles:
            print("https://repository.isls.org/" + article)
            response = requests.get("https://repository.isls.org/" + article)
            article_soup = BeautifulSoup(response.text, 'html.parser')

            citation_author = article_soup.find_all("meta", attrs={'name': "DC.creator"})
            authors = []
            for author in citation_author:
                authors.append(author["content"])

            citation_publication_date = utils.get_meta_info(article_soup, "DCTERMS.issued")
            citation_doi = utils.get_meta_info(article_soup, "DC.identifier")
            abstract = utils.get_meta_info(article_soup, "DCTERMS.abstract")

            if abstract is None:
                abstract = article_soup.find_all(class_="dc_description_abstract")
                if len(abstract) > 0:
                    abstract = abstract[-1].text

            citation_language = utils.get_meta_info(article_soup, "DCTERMS.language")
            citation_publisher = utils.get_meta_info(article_soup, "DCTERMS.publisher")
            citation_title = utils.get_meta_info(article_soup, "DCTERMS.title")
            keywords = utils.get_meta_info(article_soup, "citation_keywords")
            citation_abstract_html_url = utils.get_meta_info(article_soup, "citation_abstract_html_url")
            citation_pdf_url = utils.get_meta_info(article_soup, "citation_pdf_url")

            if citation_pdf_url is None:
                citation_pdf_url = article_soup.select('a[href^="/bitstream"]')
                if len(citation_pdf_url) > 0:
                    citation_pdf_url = citation_pdf_url[0]["href"]
                else:
                    continue

            # try to get pages
            if citation_pdf_url is not None:
                pdf_name = citation_pdf_url.split("/")[-1]
                if pdf_name:
                    pdf_name = pdf_name[:-4].split("-")
                    citation_firstpage = pdf_name[0] if len(pdf_name) >= 1 else -1
                    citation_lastpage = pdf_name[1] if len(pdf_name) > 1 else -1

                r = requests.get(citation_pdf_url)

                citation_conference_title = citation_conference_title.replace("\n", "")

                Path("./pdfs/" + citation_conference_title).mkdir(parents=True, exist_ok=True)
                title = citation_doi.replace("https://doi.dx.org/", "").replace("/", "_")
                with open("./pdfs/" + citation_conference_title + "/" + title + ".pdf", 'wb') as f:
                    f.write(r.content)

            result.append({
                'publisher': citation_publisher,
                'title': citation_title,
                'doi': citation_doi,
                'language': citation_language,
                'abstract_url': citation_abstract_html_url,
                'pdf_url': citation_pdf_url,
                'start_page': citation_firstpage,
                'last_page': citation_lastpage,
                'authors': authors,
                'keywords': keywords,
                'abstract': abstract,
                'date': citation_publication_date,
                'conf_title': citation_conference_title})

        with open("./pdfs/" + citation_conference_title + "/meta.json", 'w', encoding='UTF8') as f:
            json.dump(result, f)
    return result


def acm(link):
    result = []
    response = requests.get(link)
    html_soup = BeautifulSoup(response.text, 'html.parser')
    books = html_soup.select('a[href^="/doi/proceedings/"]')
    for book in books:
        print("book: " + "https://dl.acm.org" + book['href'])
        response_book = requests.get("https://dl.acm.org" + book['href'])
        soup_book = BeautifulSoup(response_book.text, 'html.parser')
        excluded = []

        subsections = soup_book.select('a[href*="?tocHeading"]')
        for subsection_link in subsections:
            # "https://dl.acm.org" + book['href'] + "?tocHeading=heading2",
            article_list, excluded = acm_articles("https://dl.acm.org" + subsection_link['href'], book['href'], excluded)
            result.extend(article_list)

    return result


def acm_articles(link, doi, excluded_dois=[]):
    result = []
    to_exclude = []
    response_book = requests.get(link)
    soup_book = BeautifulSoup(response_book.text, 'html.parser')
    article_href = doi.replace("/proceedings", "") + "."
    chapters = soup_book.select('a[href^="{0}"]'.format(article_href))
    for chapter in chapters:
        time.sleep(2)
        if chapter['href'] in excluded_dois:
            continue
        else:
            to_exclude.append(chapter['href'])
        print("chapter: " + "https://dl.acm.org" + chapter['href'])
        response_chapter = requests.get("https://dl.acm.org" + chapter['href'])
        soup_article = BeautifulSoup(response_chapter.text, 'html.parser')
        title = soup_article.find(class_="citation__title").text
        author_names_list = []
        author_names = soup_article.find_all(class_="author-name")
        for name in author_names:
            author_names_list.append(name.get("title"))
        author_aff_list = []
        author_affiliation = soup_article.find_all(class_="loa_author_inst")
        for aff in author_affiliation:
            par = aff.find("p")
            if par is not None:
                author_aff_list.append(aff.find("p").text)
            else:
                author_aff_list.append("-")
        date = soup_article.find(class_="epub-section__date").text
        pages = soup_article.find(class_="epub-section__pagerange").text
        if pages is not None:
            pages = pages[7:].split('–') # special -
            if len(pages) == 2:
                start_page = pages[0].strip()
                last_page = pages[1].strip()
            else:
                start_page = pages[0]
                last_page = "-"

        doi = "https://dl.acm.org" + chapter['href']
        abstract_div = soup_article.find(class_="abstractInFull")
        abstract = ""
        if abstract_div is not None:
            abstract = abstract_div.find("p").text
        conf_title = soup_article.find(class_="epub-section__title").text
        result.append({
                "title": title,
                "start_page": start_page,
                "last_page": last_page,
                "date": date,
                "doi": doi,
                "abstract": abstract,
                "authors": author_names,
                "institutions": author_aff_list,
                "conf_title": conf_title
        })
    return result, to_exclude


def springer(link):
    result = []
    try:
        response = requests.get(link)
        html_soup = BeautifulSoup(response.text, 'html.parser')
        books = html_soup.select('a[href^="/book"]')
        for book in books:
            href = book["href"]
            book = "https://link.springer.com{0}".format(href)
            response_book = requests.get(book)
            soup_book = BeautifulSoup(response_book.text, 'html.parser')
            # pages
            no_pages = soup_book.find(class_="test-maxpagenum")
            chapters = []
            if no_pages is not None:
                no_pages = int(no_pages.text)
                for page in range(1, no_pages + 1):
                    book_page = "https://link.springer.com{0}?page={1}#toc".format(href, str(page))
                    response_page = requests.get(book_page)
                    soup_page = BeautifulSoup(response_page.text, 'html.parser')
                    chapters.extend(soup_page.select('a[href^="/chapter"]'))
            else:
                chapters = soup_book.select('a[href^="/chapter"]')
            for chapter in chapters:
                chapter = "https://link.springer.com{0}".format(chapter["href"])
                response_chapter = requests.get(chapter)
                soup_chapter = BeautifulSoup(response_chapter.text, 'html.parser')

                citation_publisher = soup_chapter.find("meta", attrs={'name': "citation_publisher"})["content"]
                citation_title = soup_chapter.find("meta", attrs={'name': "citation_title"})["content"]
                citation_doi = soup_chapter.find("meta", attrs={'name': "citation_doi"})["content"]
                citation_language = soup_chapter.find("meta", attrs={'name': "citation_language"})["content"]
                citation_abstract_html_url = soup_chapter.find("meta", attrs={'name': "citation_abstract_html_url"})[
                    "content"]
                citation_fulltext_html_url = soup_chapter.find("meta", attrs={'name': "citation_fulltext_html_url"})[
                    "content"]
                citation_pdf_url = soup_chapter.find("meta", attrs={'name': "citation_pdf_url"})["content"]
                citation_springer_api_url = soup_chapter.find("meta", attrs={'name': "citation_springer_api_url"})[
                    "content"]
                citation_firstpage = soup_chapter.find("meta", attrs={'name': "citation_firstpage"})["content"]
                citation_lastpage = soup_chapter.find("meta", attrs={'name': "citation_lastpage"})["content"]
                description = ""
                if soup_chapter.find("meta", attrs={'name': "description"}) is not None:
                    description = soup_chapter.find("meta", attrs={'name': "description"})["content"]
                citation_inbook_title = soup_chapter.find("meta", attrs={'name': "citation_inbook_title"})["content"]
                citation_publication_date = soup_chapter.find("meta", attrs={'name': "citation_publication_date"})[
                    "content"]
                citation_conference_series_id = \
                    soup_chapter.find("meta", attrs={'name': "citation_conference_series_id"})["content"]
                citation_conference_title = soup_chapter.find("meta", attrs={'name': "citation_conference_title"})[
                    "content"]
                citation_conference_sequence_num = \
                    soup_chapter.find("meta", attrs={'name': "citation_conference_sequence_num"})["content"]
                citation_conference_abbrev = soup_chapter.find("meta", attrs={'name': "citation_conference_abbrev"})[
                    "content"]

                citation_author = soup_chapter.find_all("meta", attrs={'name': "citation_author"})
                authors = []
                for author in citation_author:
                    authors.append(author["content"])

                citation_author_institution = soup_chapter.find_all("meta",
                                                                    attrs={'name': "citation_author_institution"})
                institutions = []
                for institution in citation_author_institution:
                    institutions.append(institution["content"])

                citation_author_email = soup_chapter.find_all("meta", attrs={'name': "citation_author_email"})
                emails = []
                for email in citation_author_email:
                    emails.append(email["content"])

                try:
                    abstract = soup_chapter.find(id="Par1")
                    if not abstract:
                        abstract = soup_chapter.find_all(class_="Para")
                        if len(abstract) > 0:
                            abstract = abstract[0]

                    if abstract:
                        abstract = abstract.get_text()
                    else:
                        abstract = ""
                except Exception as e1:
                    print("Exception abstract")
                    traceback.print_exc()
                    abstract = ""

                keywords_elem = soup_chapter.find_all(class_="Keyword")
                keywords = []
                for keyword in keywords_elem:
                    keywords.append(keyword.get_text())

                result.append({
                    'publisher': citation_publisher,
                    'title': citation_title,
                    'doi': citation_doi,
                    'language': citation_language,
                    'abstract_url': citation_abstract_html_url,
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
                    'description': description,
                    'inbook_title': citation_inbook_title,
                    'date': citation_publication_date,
                    'conf_series_id': citation_conference_series_id,
                    'conf_title': citation_conference_title,
                    'conf_seq_no': citation_conference_sequence_num,
                    'conf_abbr': citation_conference_abbrev})
        return result

    except Exception as e:
        print(e)
        print(link)
        print(book)
        # print(chapter)
        traceback.print_exc()
        return result


header = ['Publisher', 'Title', 'DOI', 'Language', 'Abstract URL', 'Fulltext URL', 'PDF URL', 'Springer API URL',
          'Start page', 'End page', 'Authors', 'Institutions', 'Correspond email', 'Keywords', 'Abstract',
          'Description', 'Inbook title', 'Date', 'Conf. series ID', 'Conf. title', 'Conf. sequence #', 'Conf. abbrev']


def springer_json():
    confs = [
        'aied',
        'its',
        'ectel'
    ]

    for conf in confs:
        print("https://link.springer.com/conference/" + conf)
        result = springer("https://link.springer.com/conference/" + conf)

        with open(conf + '1.json', 'w', encoding='UTF8') as f:
            json.dump(result, f)
            print('done')


def acm_json():
    confs = [
        'lak',
        'sigcse',
        'l-at-s'
    ]
    for conf in confs:
        print('https://dl.acm.org/conference/' + conf)
        result = acm('https://dl.acm.org/conference/' + conf)
        with open(conf + '1.json', 'w', encoding='UTF8') as f:
            json.dump(result, f)
            print('done')


def isls_json():
    result = isls('https://repository.isls.org/')
    with open('isls.json', 'w', encoding='UTF8') as f:
        json.dump(result, f)
        print('done')


# springer_json()
acm_json()
# isls_json()
