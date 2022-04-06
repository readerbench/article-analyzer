import csv
import json

translate_conf = [
    {"csv": "Publisher", "json": "publisher"},
    {"csv": "Title", "json": "title"},
    {"csv": "DOI", "json": "doi"},
    {"csv": "Language of Original Document", "json": "language"},
    # {"csv": "", "json": "abstract_url"},
    # {"csv": "", "json": "full_text"},
    {"csv": "Link", "json": "pdf_url"},
    # {"csv": "", "json": "spring_api_url"},
    {"csv": "Page start", "json": "start_page"},
    {"csv": "Page end", "json": "last_page"},
    {"csv": "\ufeffAuthors", "json": "authors"},
    {"csv": "Affiliations", "json": "institutions"},
    {"csv": "Correspondence Address", "json": "correspond_email"},
    {"csv": "Author Keywords", "json": "keywords"},
    {"csv": "Abstract", "json": "abstract"},
    # {"csv": "", "json": "description"},
    # {"csv": "", "json": "inbook_title"},
    {"csv": "Year", "json": "date"},
    # {"csv": "", "json": "conf_series_id"},
    {"csv": "Source title", "json": "conf_title"},
    {"csv": "Conference code", "json": "conf_seq_no"},
    {"csv": "Abbreviated Source Title", "json": "conf_abbr"}
]

translate_journal = [
    {"csv": "Source title", "json": "journal_name"},
    {"csv": "Document Type", "json": "type"},
    {"csv": "Volume", "json": "volume"},
    {"csv": "Publisher", "json": "publisher"},
    {"csv": "Title", "json": "title"},
    {"csv": "DOI", "json": "doi"},
    {"csv": "Language of Original Document", "json": "language"},
    {"csv": "Page start", "json": "start_page"},
    {"csv": "Page end", "json": "last_page"},
    # {"csv": "", "json": "pages"},
    {"csv": "\ufeffAuthors", "json": "authors"},
    {"csv": "Affiliations", "json": "institutions"},
    {"csv": "Correspondence Address", "json": "correspond_email"},
    {"csv": "Author Keywords", "json": "keywords"},
    {"csv": "Abstract", "json": "abstract"},
    {"csv": "Year", "json": "date"},
    # {"csv": "", "json": "online_date"},
    {"csv": "Link", "json": "url"},
    {"csv": "Art. No.", "json": "art_no"}
]


def write_to_json(path, result):
    with open(path + 'meta.json', 'w', encoding='UTF8') as f:
        json.dump(result, f)
        print('done')


def read_from_csv(path, names, translation):
    result = []
    for name in names:
        with open(path + name, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                r = {}
                for elem in translation:
                    if elem["csv"] in ["\ufeffAuthors", "Affiliations"]:
                        r[elem["json"]] = row[elem["csv"]].split(",")
                    else:
                        r[elem["json"]] = row[elem["csv"]]
                result.append(r)
    write_to_json(path, result)