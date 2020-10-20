import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from tqdm import tqdm
import isbnlib
from lxml import etree
from io import StringIO, BytesIO

gr_limiter = RateLimiter(max_calls=1, period=1)
session = get_session()

def get_book(book_id):
    with gr_limiter:
        key = CREDENTIALS['goodreads']
        try:
            url = f"https://www.goodreads.com/book/show.xml?id={book_id}&key={key}"
            res = session.get(url, timeout=60).content
            if res:
                return etree.parse(BytesIO(res))
            else:
                return None
        except Exception as e:
            logging.error('failed to fetch book data', exc_info=e)
            return None

        
STATED_IN = 'P248'
GR = 'Q2359213'
RETRIEVED = 'P813'

def make_quals(repo, name):
    quals = []
    if name:
        named_as_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
        named_as_claim.setTarget(name)
        quals.append(named_as_claim)
    quals.append(point_in_time_claim(repo))        
    return quals
    

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/books.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

GR_BOOK_ID = 'P2969'
NAMED_AS = 'P1810'

for g in tqdm(generator):
    d = g.get()
    gr_books = get_valid_claims(d, GR_BOOK_ID)
    for book in gr_books:
        book_id = book.getTarget()
        if not book_id:
            continue
        gr_book = get_book(book_id)
        if not gr_book:
            continue
        title = gr_book.find("book/title")
        if title is not None and title.text:
            quals = make_quals(repo, title.text.strip())
            update_qualifiers(repo, book, quals, "update goodreads book data")

