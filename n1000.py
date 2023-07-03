import json
from elasticsearch import Elasticsearch
import re
import csv
import os
import ast
import requests
import spacy
import eval_articles
import sys
nlp = spacy.load('en_core_web_lg')



def get_ref_entities():
    with open('relevant_entities.txt', 'r') as f:
        entities = [e.strip() for e in f.readlines()]
        return [nlp(e) for e in entities]

ref_entities = get_ref_entities()


def build_parent_graph(sections):
    graph = {}
    for section in sections:
        s = graph[section['parent']] if section['parent'] else set()
        s.add(section['parent'])
        graph[section['index']] = s
    return graph


def get_all_id_heading_text(es):
    query = {"_source": ["description", "sections.heading", "sections.text", "sections.index", "sections.parent", "title"], "size": 100,
            "query": {
                "bool": {
                    "must": [
                        { "exists": {"field": "sections"} },   
                        { "match": {
                            "publicationdateyear": {
                                "query": str(largeN_year) + "/01/01 00:00:00"
                            }
                        } }
                    ]
                }
            } 
        }

    res = es.search(index='eric-articles', body=query, scroll='60s', request_timeout=60)
    scroll_id = res['_scroll_id']

    heading_and_text = []
    for i, hit in enumerate(res['hits']['hits']):
        source = hit['_source']
        indices_of_interesting_sections = {}
        for section in source['sections']:            
            heading = section['heading'].lower()
            if heading.startswith('meth') or heading.startswith('participa') or heading.startswith('cor') or \
                'method' in heading or ('material' in heading and 'supplementary' not in heading) or 'participant' in heading or 'study' in heading or \
                'sample' in heading or 'result' in heading or 'data' in heading:
                indices_of_interesting_sections[section['index']] = [heading, section['text']]
        sections_parent_graph = build_parent_graph(source['sections'])
        for section in source['sections']:
            if section['index'] in indices_of_interesting_sections:
                continue
            for parent in sections_parent_graph[section['index']]:
                if parent in indices_of_interesting_sections:
                    indices_of_interesting_sections[parent][1] += ' ' + section['text']
        for _, (heading, text) in indices_of_interesting_sections.items():
            if text:
                heading_and_text.append((hit['_id'], heading, text, source['title']))
        if source['description']:
            heading_and_text.append((hit['_id'], 'description', source['description'], source['title']))
    
    while len(res['hits']['hits']):
        res = es.scroll(scroll_id=scroll_id, scroll='60s')
        for i, hit in enumerate(res['hits']['hits']):
            source = hit['_source']
            indices_of_interesting_sections = {}
            for section in source['sections']:            
                heading = section['heading'].lower()
                if heading.startswith('meth') or heading.startswith('participa') or heading.startswith('cor') or \
                    'method' in heading or ('material' in heading and 'supplementary' not in heading) or 'participant' in heading or 'study' in heading or \
                    'sample' in heading or 'result' in heading or 'data' in heading:
                    indices_of_interesting_sections[section['index']] = [heading, section['text']]
            sections_parent_graph = build_parent_graph(source['sections'])
            for section in source['sections']:
                if section['index'] in indices_of_interesting_sections:
                    continue
                for parent in sections_parent_graph[section['index']]:
                    if parent in indices_of_interesting_sections:
                        indices_of_interesting_sections[parent][1] += ' ' + section['text']
            for _, (heading, text) in indices_of_interesting_sections.items():
                if text:
                    heading_and_text.append((hit['_id'], heading, text, source['title']))  
            if source.get('description', None):
                heading_and_text.append((hit['_id'], 'description', source['description'], source['title']))

    print("Total articles per year: " + str(len(heading_and_text)))
    return heading_and_text


def get_sections_with_numbers(id_heading_text):
    r = re.compile(r"[Nn]\s?=\s?[0-9]{3}[0-9]+")
    r2 = re.compile(r"[Nn]\s?=\s?[0-9]+(,[0-9]{3})+")
    results = []
    for id, heading, text, title in id_heading_text:
        if r.search(text):
            results.append((id, heading, text, title))
        elif r2.search(text):
            results.append((id, heading, text, title))
    return results


def remove_copyright(id_heading_text):
    r = re.compile(r"©\s?[0-9]{4}")
    for i, e in enumerate(id_heading_text):
        id, heading, text = e
        text = re.sub(r, '', text)
        id_heading_text[i] = (id, heading, text)


def remove_in_year(id_heading_text):
    r = re.compile(r"[iI]n [0-9]{4}")
    for i, e in enumerate(id_heading_text):
        id, heading, text = e
        text = re.sub(r, '', text)
        id_heading_text[i] = (id, heading, text)


def remove_year_from_citations(id_heading_text):
    r = re.compile(r",\s?[0-9]{4}")
    for i, e in enumerate(id_heading_text):
        id, heading, text = e
        text = re.sub(r, '', text)
        id_heading_text[i] = (id, heading, text)


def remove_year_from_inside_parathesis(id_heading_text):
    r = re.compile(r"([0-9]{4})")
    for i, e in enumerate(id_heading_text):
        id, heading, text = e
        text = re.sub(r, '', text)
        id_heading_text[i] = (id, heading, text)


def remove_irrelevent_4_numbers(id_heading_text):
    r_copyright = re.compile(r"©\s?[0-9]{4}")
    r_in_year = re.compile(r"[iI]n [0-9]{4}")
    r_in_citations_with_comma = re.compile(r",\s*[0-9]{4}")
    r_in_parathesis = re.compile(r"\([0-9]{4}\)")
    r_month_before_year = re.compile(r"\s[A-Z][a-z]+\s*[0-9]{4}")
    r_ms_after = re.compile(r"[0-9]+[\W]*ms")
    r_numbers_between_minus = re.compile(r"-[0-9]+-")
    r_pixels = re.compile(r"[0-9]*,*[0-9]+\s*×\s*[0-9]*,*[0-9]+\s*pixel")
    r_miliseconds = re.compile(r"[0-9]*,*[0-9]+\s*ms")
    r_hertz = re.compile(r"[0-9]*,*[0-9]+\s*[Hh][Zz]")
    r_citation_et_al = re.compile(r"al\.,\s*[0-9]{4}")
    r_citation = re.compile(r"[A-Z][a-z]+,\s*[0-9]{4}")
    r_lines_in_front = re.compile(r"-|–[0-9]+")
    r_f_stuff = re.compile(r"F\s*\([0-9]+(,?[0-9]{3})*")
    r_number_point_number = re.compile(r"[0-9]+\.[0-9]+")
    r_multiply = re.compile(r"[0-9]*,*[0-9]+\s*×\s*[0-9]*,*[0-9]+")
    r_dolar_remove = re.compile(r"\$[0-9]+,*[0-9]+")
    r_from_to = re.compile(r"[Ff]rom\s*[0-9]{4}\s*to\s*[0-9]{4}")
    r_citation_v2 = re.compile(r"\([A-Z][a-z]+\s*[^\)]+[0-9]{4}")
    r_and_years = re.compile(r"\s*[0-9]{4}\s*[Aa][Nn][Dd]\s*[0-9]{4}")
    r_metrics = re.compile(r"(W|SD|M)\s.\s[0-9]+(,*[0-9])+")
    r_F = re.compile(r"F[0-9]+(,*[0-9])+")
    r_numbers_one_after_another = re.compile(r"([0-9]+[^a-zA-Z0-9,]+[0-9]+)+")
    for i, e in enumerate(id_heading_text):
        id, heading, text, title = e
        text = re.sub(r_copyright, '', text)
        text = re.sub(r_in_year, '', text)
        text = re.sub(r_in_citations_with_comma, '', text)
        text = re.sub(r_in_parathesis, '', text)
        text = re.sub(r_month_before_year, '', text)
        text = re.sub(r_ms_after, '', text)
        text = re.sub(r_numbers_between_minus, '', text)
        text = re.sub(r_pixels, '', text)
        text = re.sub(r_miliseconds, '', text)
        text = re.sub(r_hertz, '', text)
        text = re.sub(r_citation_et_al, '', text)
        text = re.sub(r_citation, '', text)
        text = re.sub(r_lines_in_front, ' ', text)
        text = re.sub(r_f_stuff, '', text)
        text = re.sub(r_number_point_number, '', text)
        text = re.sub(r_multiply, '', text)
        text = re.sub(r_dolar_remove, '', text)
        text = re.sub(r_from_to, '', text)
        text = re.sub(r_citation_v2, '', text)
        text = re.sub(r_and_years, '', text)
        text = re.sub(r_metrics, '', text)
        text = re.sub(r_F, '', text)
        text = re.sub(r_numbers_one_after_another, '', text)
        id_heading_text[i] = (id, heading, text, title)


def get_parts_for_a_re(r, id, heading, text, results, title):
    if r.search(text) is None:
        return
    texts_with_numbers = []
    part_of_text = text
    while True:
        match = r.search(part_of_text)
        if match is None:
            break
        start = match.start()
        word_length = 0
        group_match = match.group(0).strip()
        doc = nlp(part_of_text)
        for w in doc:
            if w.text == group_match:
                # print("intra", w.head, w.head.pos_)
                if w.head.pos_ == "NOUN":
                    noun_head = w.head
                    if noun_head.has_vector:
                        for e in ref_entities:
                            if e.similarity(noun_head) > 0.7:
                                if not ("bootstrap" in part_of_text[max(0, start - 50):(start + 54)]):
                                    texts_with_numbers.append(part_of_text[max(0, start - 50):(start + 54)])
                                break
                word_length = len(w.text)
                break
        if word_length == 0:
            word_length = len(group_match)

        part_of_text = part_of_text[start+word_length:]

    if texts_with_numbers:
        results.append((id, heading, texts_with_numbers, title))


def get_parts_of_texts_with_numbers(id_heading_text):
    r1 = re.compile(r"[=|\s][1-9][0-9]{2}[0-9]+[\W]")
    r2 = re.compile(r"[0-9]+(,[0-9]{3})+[\W]")
    r3 = re.compile(r"[T|t]housand|[M|m]illion|[B|b]illion")
    results = []
    count = 0
    length = len(id_heading_text)
    for id, heading, text, title in id_heading_text:
        count += 1
        get_parts_for_a_re(r1, id, heading, text, results, title)
        get_parts_for_a_re(r2, id, heading, text, results, title)
        get_parts_for_a_re(r3, id, heading, text, results, title)
        if count % 100 == 0:
            print(f"Done {count}/{length}..")
    return results



def main_extract_n1000(es):
    id_heading_text = get_all_id_heading_text(es)  # TODO aici trebuie sa returneze si titlul, iar urmatoarele functii tb sa stie asta
    certain_n_1000 = get_sections_with_numbers(id_heading_text)
    certain_ids = set([id for id, heading, text, title in certain_n_1000])
    filtered_id_heading_text = [x for x in id_heading_text if x[0] not in certain_ids]
    remove_irrelevent_4_numbers(filtered_id_heading_text)
    with open('potential_n1000.csv', 'w') as f:
        csv_writer = csv.writer(f)
        for id, heading, text, title in get_parts_of_texts_with_numbers(filtered_id_heading_text):
            for t in text:
                csv_writer.writerow([id, heading, [t], title])

specific_id_to_class = {}


def main_label_everything(es):
    id_heading_text = get_all_id_heading_text(es)
    certain_n_1000 = get_sections_with_numbers(id_heading_text)
    certain_ids = set([id for id, heading, text in certain_n_1000])

    filtered_id_heading_text = [x for x in id_heading_text if x[0] not in certain_ids]
    remove_irrelevent_4_numbers(filtered_id_heading_text)
    
    n1000_ids = set()
    n1000_ids.update(certain_ids)
    count = 0
    for id, heading, text in get_parts_of_texts_with_numbers(filtered_id_heading_text):
        if text:
            n1000_ids.add(id)

    with open("ids_n1000.txt", "w") as f:
        for id in n1000_ids:
            f.write(id + "\n")


def insert_n1000_doc(es, id):
    document = es.get(index='articles', id=id)['_source']
    new_document = {}
    new_document["date"] = document["date"]
    new_document["keywords"] = document.get("keywords", [])
    new_document["language"] = document.get("language", "English")
    new_document["title"] = document["title"]
    new_document["institutions"] = document.get("institutions", [])
    new_document["authors"] = document.get("authors", [])
    new_document["conf_abbr"] = document["conf_abbr"]
    new_document["publisher"] = document["publisher"]
    new_document["doi"] = document["doi"]
    new_document["is_educational"] = document["is_educational"]
    new_document["normalized_authors"] = document.get("normalized_authors", [])
    es.update(index='automated_n1000', id=id, body={"doc": new_document, "doc_as_upsert": True})


def main_insert_n1000_docs_by_id(es):
    with open("ids_n1000.txt", "r") as f:
        for line in f.readlines():
            id = line.strip()
            insert_n1000_doc(es, id)


def get_duckling_ents(text):
    data = {
        'locale': 'en_US',
        'text': text,
        'dims': ["quantity","numeral"]
    }

    response = requests.post('http://hidden_server_path/parse', data=data)
    json_response = response.json()
    if not json_response:
        return None

    results = []
    for hit in json_response:
        if hit['dim'] in ['number', 'quantity', 'numeral']:
            if 'value' in hit['value']:
                if type(hit['value']['value']) in [int, float] and hit['value']['value'] > 1000:
                    results.append((hit['start'], hit['end'], hit['value']['value']))

    return results


def compute_rules_and_t5_predictions():
    y_pred_rules = []
    with open("potential_n1000.csv", "r") as f:
        reader = csv.reader(f)
        for row in reader:
            y_pred_rules.append((row[0], row[3]))  # (id, titlul-ul of the potential largeN)
            
    print("T5 compute results")
    y_pred_t5 = eval_articles.evaluate_with_t5(corpus_file, y_pred_rules, largeN_year)

    return y_pred_t5, y_pred_rules
    
corpus_file = "eric.json"
largeN_year = 2022 # select the year for which all articles will be verified for potential largeN

if __name__ == '__main__':
    es = Elasticsearch(
        hosts=None,
        http_auth=None,
        scheme=None,
        port=None,
    ) # hidden for security reasons
    
    largeN_year = int(sys.argv[1])

    main_extract_n1000(es)    # generates potential_n1000.csv  which contains the id, heading and text of the potential largeN articles using heuristics
    compute_rules_and_t5_predictions()

