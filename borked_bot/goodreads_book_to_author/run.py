import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from tqdm import tqdm
import isbnlib
from lxml import etree
import logging
import re
from io import StringIO, BytesIO

gr_limiter = RateLimiter(max_calls=1, period=1)
session = get_session()

def get_book_data(book_id):
    with gr_limiter:
        key = CREDENTIALS['goodreads']
        try:
            url = f"https://www.goodreads.com/book/show.xml?id={book_id}&key={key}&format=json"
            res = session.get(url, timeout=60).content
            if res:
                return etree.parse(BytesIO(res))
            else:
                return None
        except Exception as e:
            logging.error('failed to fetch book data', exc_info=e)
            return None



def clean_name(name):
    if not name:
        return name
    return re.sub("[-'`\s,.]", "", name.lower())

STATED_IN = 'P248'
INFER_FROM = 'P3452'
GR = 'Q2359213'
RETRIEVED = 'P813'
NAMED_AS = 'P1810'

def make_sources(repo, book_id):
    claims = []
    claims.append(retrieved_claim(repo))
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    gr_target = pywikibot.ItemPage(repo, GR)
    stated_in_claim.setTarget(gr_target)
    claims.append(stated_in_claim)
    infer_from_claim = pywikibot.Claim(repo, INFER_FROM)
    infer_from_claim.setTarget(book_id)
    claims.append(infer_from_claim)
    return claims
    

def make_quals(repo, name):
    quals = []
    named_as = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
    named_as.setTarget(name)
    quals.append(named_as)
    return quals
    

    
WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/books_with_authors.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

GR_BOOK_ID = 'P2969'
GR_AUTHOR_ID = 'P2963'
AUTHOR_ID = 'P50'

done_authors = set()
for g in tqdm(generator):
    d = g.get()
    book_claims = get_valid_claims(d, GR_BOOK_ID)
    author_claims = get_valid_claims(d, AUTHOR_ID)
    if len(author_claims) > 1:
        # we aren't trying to resolve this case
        continue
    author_claim = author_claims[0]
    author = author_claim.getTarget()
    author_wd_id = author.title()
    if author_wd_id in done_authors:
        continue
    for book_id_claim in book_claims:
        book_id = book_id_claim.getTarget()
        if not book_id:
            continue
        book = get_book_data(book_id)
        if not book:
            continue
        title = book.find("book/title").text
        authors = [(a.find("name").text, a.find("id").text) for a in book.find("book/authors")]
        if len(authors) > 1:
            # we aren't trying to resolve this case
            continue
        author_name, author_id = authors[0]
        clean_author_name = clean_name(author_name)
        wd_author = author_claim.getTarget().get()
        author_names = set(wd_author['labels'].values()).union(set(sum(list(wd_author['aliases'].values()),[])))
        author_names = [clean_name(n) for n in author_names]
        if author_name and author_id and clean_author_name in author_names:
            print('hit')
            done_authors.add(author_wd_id)
            sources = make_sources(repo, g)
            quals = make_quals(repo, author_name)
            add_claim(repo, author, GR_AUTHOR_ID, str(author_id), sources, quals, comment=f"import goodreads author id via book {g.title()} and goodreads book {book_id}")
            break # done with this author anyways
        else:
            print('miss', author_name, author_names, author_wd_id)
            
