import json

from bs4 import BeautifulSoup as soup
from urllib.request import urlopen as uReq


def run():
    dict = {}
    for pp in range(1, 16):
        url = f"https://codeforces.com/contests/page/{pp}"
        uClient = uReq(url)
        page_html = uClient.read()
        uClient.close()
        page_soup = soup(page_html, "html.parser")
        container = page_soup.find("div", {"class": "contests-table"})
        items = container.findAll('tr')
        for i in items[1:]:
            td_content = i.findAll('td')
            contest_id = td_content[0].find('a')['href'].split('/')[-1]
            a_tags = td_content[1].findAll('a')
            authors = []
            for x in a_tags:
                authors.append(x['href'].split('/')[-1])
            if 'vovuh' in authors:
                authors.append('pikmike')
            dict[contest_id]=authors

    with open('./data/authors.json', 'w') as json_file:
        json.dump(dict, json_file)