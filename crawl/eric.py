import requests
import json
import os

from bs4 import BeautifulSoup
from time import sleep

DATABASE_FOLDER = "D:\\Proiecte Facultate\\EducationProject\\ERIC\\Database"
PDF_SAVE_BASE = "D:\\Proiecte Facultate\\EducationProject\\ERIC\\pdfs\\"
PDF_DOWNLOAD_BASE = "https://files.eric.ed.gov/fulltext/"

def save_pdf(id_, year, full_text, url = None):
    pdf_url = None
    if full_text == 1:
        pdf_url = PDF_DOWNLOAD_BASE + id_ + ".pdf"
    # elif url:
    #     pdf_url = url

    if not pdf_url:
        print ("Not found: ", id_, " (no full pdf available)")
        print ("=================================")
        return False

    print (pdf_url)
    filepath = PDF_SAVE_BASE + str(year) + "\\" + id_ + ".pdf"
    if not os.path.exists(filepath):
        r = requests.get(pdf_url, stream = True)
        with open(filepath, "wb") as f:
            f.write(r.content)
            print ("Found: ", pdf_url)
    else:
        print ("Already exists.")

    print ("=================================")
    return True


def save_json(filepath, result):
    with open(filepath, "w", encoding = 'UTF8') as f:
        json.dump(result, f)

def read_json(filepath):
    file = open(filepath)
    result = json.load(file)
    return result

def get_database_files():
    files = []

    for (dirpath, dirnames, filenames) in os.walk(DATABASE_FOLDER):
        for file in filenames:
            files.append(os.path.join(dirpath, file))

    return files

def read_file(filename):
    with open(filename, "r", encoding = 'UTF8') as f:
        data = f.read()
    return data

def get_records(id_, fields = None):
    url = "https://api.ies.ed.gov/eric/?"
    url += "search=id:" + id_ + "&rows=1" + "&format=json&start=0"
    if fields:
        url += "&fields=" + ", ".join(fields)

    response = requests.get(url).json()
    try:
    	metadata = response["response"]["docs"][0]
    except:
    	metadata = None
    
    return metadata


def get_eric_fields():
    fields = ["id", "title", "author", "source",  "sourceid", "publicationdateyear", 
        "description", "subject", "peerreviewed", "abstractor", "audience",
        "e_fulltextauth", "e_yearadded", "educationlevel", "institution", "isbn",
        "issn", "language", "publicationtype", "publisher", "sponsor", "url"]
    return fields

def main():
    fields = get_eric_fields()
    # all_data = []
    # total_pdfs_found = 0

    files = get_database_files()
    # files = files[55:56]
    # print (files)
    for f in files:
        print (f)
        year = f.split("\\")[-1].split(".")[0][-4:]
        if not os.path.exists(PDF_SAVE_BASE + str(year)):
            os.makedirs(PDF_SAVE_BASE + str(year))

        year_files = []
        for (dirpath, dirnames, filenames) in os.walk(PDF_SAVE_BASE + str(year)):
            for file in filenames:
                year_files.append(os.path.join(file))

        if "meta.json" in year_files:
            year_data = read_json(PDF_SAVE_BASE + str(year) + "\\meta.json")
        else:
            year_data = []

        if "pdfs_not_found.json" in year_files:
            pdfs_not_found = read_json(PDF_SAVE_BASE + str(year) + "\\pdfs_not_found.json")
        else:
            pdfs_not_found = []

        if len(year_files) > 2:
            pdfs_found = len(year_files) - 2
        else:
            pdfs_found = 0

        data = read_file(f)
        bs_data = BeautifulSoup(data, "xml")
        ids = bs_data.find_all("dc:identifier", {"scheme": "eric_accno"})
        print ("Data: ", len(ids))

        print ("=========== Initializations ===========")
        print ("Existing metadata: " + str(len(year_data)))
        print ("Pdfs not found: " + str(len(pdfs_not_found)))
        print ("Pdfs found: " + str(pdfs_found))

        existing_ids_ = [e['id'] for e in year_data]

        for idx, elem in enumerate(ids):
            id_ = elem.text

            if id_ in existing_ids_:
                print ("ID: " + id_ + " - Already processed...")
                continue
            else:
                print (id_)

            metadata = get_records(id_, fields)
            if not metadata:
            	print ("ID: " + id_ + " negasit")
            	continue

            if "e_fulltextauth" in metadata and metadata["e_fulltextauth"] == 1 and "url" in metadata:
                print ("ERROR: id_: ", id_, " - year: ", year)
                pdfs_not_found.append({"error": "FULL TEXT AND URL", "id_": id_})

            if "e_fulltextauth" in metadata:
                flag = save_pdf(id_, year, metadata["e_fulltextauth"])
            else:
                print ("Not found: ", id_, " (no full pdf available)")
                print ("=================================")
                flag = False
            if flag:
                pdfs_found += 1
            else:
                pdfs_not_found.append(id_)

            year_data.append(metadata)
            # all_data.append(metadata)

            save_json(PDF_SAVE_BASE + str(year) + "\\meta.json", year_data)
            save_json(PDF_SAVE_BASE + str(year) + "\\pdfs_not_found.json", pdfs_not_found)

            if idx % 25 == 0:
                sleep(2)

        # total_pdfs_found += pdfs_found

        print ("Statistici fisier: ", f)
        print ("Numar total: ", len(year_data))
        print ("Pdf-uri gasite: ", pdfs_found)
        print ("Pdf-uri negasite: ", len(pdfs_not_found))
        print ("Procent: ", str(100 * pdfs_found / len(year_data)) + "%")

        save_json(PDF_SAVE_BASE + str(year) + "\\meta.json", year_data)
        save_json(PDF_SAVE_BASE + str(year) + "\\pdfs_not_found.json", pdfs_not_found)
        print ("DONE FILE: ", f)

    # save_json(PDF_SAVE_BASE + "\\meta.json", all_data)
    # print ("=================================")
    # print ("Statistici generale:")
    # print ("Numar total: ", len(all_data))
    # print ("Pdf-uri gasite: ", total_pdfs_found)
    # print ("Procent: ", str(100 * total_pdfs_found / len(all_data)) + "%")


if __name__ == "__main__":
    main()
    # test()


def test():
    fields = get_eric_fields()
    
    id_ = "ED030765"
    metadata = get_records(id_, fields)

    print (metadata)

    # if "e_fulltextauth" in metadata:
    #     print (metadata["e_fulltextauth"])
    # if "url" in metadata:
    #     print (metadata["url"])

    # year = 2021

    # if not os.path.exists(PDF_SAVE_BASE + str(year)):
    #     os.makedirs(PDF_SAVE_BASE + str(year))

    # save_pdf(id_, year, metadata["e_fulltextauth"])


