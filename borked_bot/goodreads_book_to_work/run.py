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

def get_work(book_id):
    with gr_limiter:
        key = CREDENTIALS['goodreads']
        try:
            url = f"https://www.goodreads.com/book/id_to_work_id/{book_id}?key={key}&format=json"
            res = session.get(url, timeout=60).json()
            if res:
                return res['work_ids'][0]
            else:
                return None
        except:
            return None


STATED_IN = 'P248'
GR = 'Q2359213'
RETRIEVED = 'P813'

def make_sources(repo):
    claims = []
    claims.append(retrieved_claim(repo))
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    isbn_target = pywikibot.ItemPage(repo, GR)
    stated_in_claim.setTarget(isbn_target)
    claims.append(stated_in_claim)
    return claims
    

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/unlinked_gr_books.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

GR_BOOK_ID = 'P2969'
GR_WORK_ID = 'P8383'

for g in tqdm(generator):
    d = g.get()
    book_claims = get_valid_claims(d, GR_BOOK_ID)
    used_ids = set()
    for book_id_claim in book_claims:
        book_id = book_id_claim.getTarget()
        if not book_id:
            continue
        work_id = get_work(book_id)
        if work_id and work_id not in used_ids:
            sources = make_sources(repo)
            used_ids.add(work_id)
            add_claim(repo, g, GR_WORK_ID, str(work_id), sources, comment=f"import goodreads work id from book id {book_id}")

