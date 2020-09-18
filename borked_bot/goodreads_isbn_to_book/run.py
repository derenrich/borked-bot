import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from tqdm import tqdm
import isbnlib


gr_limiter = RateLimiter(max_calls=1, period=1)
session = get_session()

def get_book(isbn):
    with gr_limiter:
        key = CREDENTIALS['goodreads']
        try:
            url = f"https://www.goodreads.com/book/isbn_to_id/{isbn}?key={key}&format=json"
            res = session.get(url, timeout=60)
            if res:
                return res.text
            else:
                return None
        except:
            return None


INFER_FROM = 'P3452'
ISBN = 'Q33057'
STATED_IN = 'P248'
GR = 'Q2359213'
RETRIEVED = 'P813'

def make_sources(repo):
    claims = []
    claims.append(retrieved_claim(repo))
    #infer_claim = pywikibot.Claim(repo, INFER_FROM)
    #isbn_target = pywikibot.ItemPage(repo, ISBN)
    #infer_claim.setTarget(isbn_target)
    #claims.append(infer_claim)
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    isbn_target = pywikibot.ItemPage(repo, GR)
    stated_in_claim.setTarget(isbn_target)
    claims.append(stated_in_claim)
    return claims
    

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/unlinked_isbns.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

ISBN_13 = 'P212'
ISBN_10 = 'P957'
GR_BOOK_ID = 'P2969'

for g in tqdm(generator):
    d = g.get()
    isbn_13_claims = get_valid_claims(d, ISBN_13)
    isbn_10_claims = get_valid_claims(d, ISBN_10)
    isbns = isbn_13_claims + isbn_10_claims
    used_isbns = set()
    tried_isbns = set()
    for isbn in isbns:
        isbn_string = isbn.getTarget()
        if not isbn_string:
            continue
        if isbnlib.is_isbn10(isbn_string) and isbnlib.to_isbn13(isbn_string) in tried_isbns:
            continue        
        book_id = get_book(isbn_string)
        tried_isbns.add(isbnlib.canonical(isbn_string))
        if book_id and book_id not in used_isbns:
            print('hit')
            sources = make_sources(repo)
            used_isbns.add(book_id)
            add_claim(repo, g, GR_BOOK_ID, book_id, sources, comment=f"import goodreads book id from ISBN: {isbn_string}")

