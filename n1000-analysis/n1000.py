import json
from elasticsearch import Elasticsearch
import re
import csv
import os
import ast
import requests
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
import spacy
from tensorflow_hub import text_embedding_column
nlp = spacy.load('en_core_web_lg')



def get_ref_entities():
    with open('relevant_entities.txt', 'r') as f:
        entities = [e.strip() for e in f.readlines()]
        return [nlp(e) for e in entities]

ref_entities = get_ref_entities()

def get_all_ids_from_n1000(es, conf_abbr=None):
    if conf_abbr:
        query = {"_source": [], "size": 100, 
                    "query": {
                        "bool": {
                            "must": [
                                { "term": {"conf_abbr": conf_abbr} }
                            ]
                        }
                    } 
                }
    else:
        query = {"_source": [], "size": 100, 
                "query": {
                    "match_all": {}
                }
            }

    res = es.search(index='n1000', body=query, scroll='60s', request_timeout=60)
    scroll_id = res['_scroll_id']

    ids = set()
    for i, hit in enumerate(res['hits']['hits']):
        ids.add(hit['_id'])
    
    while len(res['hits']['hits']):
        res = es.scroll(scroll_id=scroll_id, scroll='60s')
        for i, hit in enumerate(res['hits']['hits']):
            ids.add(hit['_id'])

    return ids


def build_parent_graph(sections):
    graph = {}
    for section in sections:
        s = graph[section['parent']] if section['parent'] else set()
        s.add(section['parent'])
        graph[section['index']] = s
    return graph


def get_all_id_heading_text(es, conf_abbr=None):
    if conf_abbr:
        query = {"_source": ["abstract", "sections.heading", "sections.text", "sections.index", "sections.parent"], "size": 100, 
                    "query": {
                        "bool": {
                            "must": [
                                { "exists": {"field": "sections"} },
                                { "term": {"conf_abbr": conf_abbr} }
                            ]
                        }
                    } 
                }
    else:
        query = {"_source": ["abstract", "sections.heading", "sections.text", "sections.index", "sections.parent"], "size": 100, 
                "query": {
                    "bool": {
                        "must": [
                            { "exists": {"field": "sections"} },
                        ]
                    }
                } 
            }

    res = es.search(index='articles', body=query, scroll='60s', request_timeout=60)
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
                heading_and_text.append((hit['_id'], heading, text))
        if source['abstract']:
            heading_and_text.append((hit['_id'], 'abstract', source['abstract']))
    
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
                    heading_and_text.append((hit['_id'], heading, text))
            if source['abstract']:
                heading_and_text.append((hit['_id'], 'abstract', source['abstract']))

    return heading_and_text


def get_sections_with_numbers(id_heading_text):
    r = re.compile(r"[Nn]\s?=\s?[0-9]{3}[0-9]+")
    r2 = re.compile(r"[Nn]\s?=\s?[0-9]+(,[0-9]{3})+")
    results = []
    for id, heading, text in id_heading_text:
        if r.search(text):
            results.append((id, heading, text))
        elif r2.search(text):
            results.append((id, heading, text))
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
        id, heading, text = e
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
        id_heading_text[i] = (id, heading, text)


def get_parts_for_a_re(r, id, heading, text, results):
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
        results.append((id, heading, texts_with_numbers))


def get_parts_of_texts_with_numbers(id_heading_text):
    r1 = re.compile(r"[=|\s][1-9][0-9]{2}[0-9]+[\W]")
    r2 = re.compile(r"[0-9]+(,[0-9]{3})+[\W]")
    r3 = re.compile(r"[T|t]housand|[M|m]illion|[B|b]illion")
    results = []
    count = 0
    length = len(id_heading_text)
    for id, heading, text in id_heading_text:
        count += 1
        get_parts_for_a_re(r1, id, heading, text, results)
        get_parts_for_a_re(r2, id, heading, text, results)
        get_parts_for_a_re(r3, id, heading, text, results)
        if count % 100 == 0:
            print(f"Done {count}/{length}..")
    return results


def main_extract_n1000_with_duckling(es):
    id_heading_text = get_all_id_heading_text(es)
    already_processed = get_all_ids_from_n1000(es)
    id_heading_text = [x for x in id_heading_text if x[0] not in already_processed]
    certain_n_1000 = get_sections_with_numbers(id_heading_text)
    certain_ids = set([id for id, heading, text in certain_n_1000])
    print(len(certain_ids))
    filtered_id_heading_text = [x for x in id_heading_text if x[0] not in certain_ids]
    remove_irrelevent_4_numbers(filtered_id_heading_text)
    results = []
    for id, heading, text in filtered_id_heading_text:
        numbers = get_duckling_ents(text)
        if numbers:
            for number in numbers:
                results.append([id, heading, [text[number[0] - 50:number[1] + 50]], number[2]])
    with open('potential_n1000_duck.csv', 'w') as f:
        csv_writer = csv.writer(f)
        csv_writer.writerows(results)


def main_extract_n1000(es):
    id_heading_text = get_all_id_heading_text(es)
    already_processed = get_all_ids_from_n1000(es)
    id_heading_text = [x for x in id_heading_text if x[0] not in already_processed]
    certain_n_1000 = get_sections_with_numbers(id_heading_text)
    certain_ids = set([id for id, heading, text in certain_n_1000])
    filtered_id_heading_text = [x for x in id_heading_text if x[0] not in certain_ids]
    remove_irrelevent_4_numbers(filtered_id_heading_text)
    with open('potential_n1000.csv', 'w') as f:
        csv_writer = csv.writer(f)
        for id, heading, text in get_parts_of_texts_with_numbers(filtered_id_heading_text):
            for t in text:
                csv_writer.writerow([id, heading, [t]])

specific_id_to_class = {}
def main_test(es):
    specific_ids = []
    with open('corpus.csv', 'r') as f:
        for line in f.readlines():
            line = line.strip()
            id, class_ = line.split(',')
            specific_id_to_class[id] = int(class_)
            specific_ids.append(id)
    test_results = {}
    id_heading_text = get_all_id_heading_text(es)
    certain_n_1000 = get_sections_with_numbers(id_heading_text)

    certain_ids = set([id for id, heading, text in certain_n_1000])
    count = 0
    for id in specific_ids:
        if id in certain_ids:
            count += 1
            test_results[id] = 2
    
   
    filtered_id_heading_text = [x for x in id_heading_text if x[0] not in certain_ids]
    remove_irrelevent_4_numbers(filtered_id_heading_text)
    
    count = 0
    for id, heading, text in get_parts_of_texts_with_numbers(filtered_id_heading_text):
        count += 1
        if text:
            test_results[id] = 1
    
    with open('test_results.csv', 'w') as g:
        writer = csv.writer(g)
        for id in specific_ids:
            if id in test_results:
                writer.writerow([id,1])
            else:
                writer.writerow([id,0])


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


def compute_confusion_matrix():
    y_true = []
    with open("corpus.csv", "r") as f:
        reader = csv.reader(f)
        for row in reader:
            y_true.append(int(row[1]))
    
    y_pred = []
    with open("test_results.csv", "r") as f:
        reader = csv.reader(f)
        for row in reader:
            y_pred.append(int(row[1]))

    print(confusion_matrix(y_true, y_pred))
    print(precision_recall_fscore_support(y_true, y_pred, average='binary'))


if __name__ == '__main__':
    es = Elasticsearch(
        hosts=None,
        http_auth=None,
        scheme=None,
        port=None,
    ) # hidden for security reasons
    
    main_test(es)
    compute_confusion_matrix()