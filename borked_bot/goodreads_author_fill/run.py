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

def get_author(author_id):
    with gr_limiter:
        key = CREDENTIALS['goodreads']
        try:
            url = f"https://www.goodreads.com/author/show.xml?key={key}&id={author_id}"
            res = session.get(url, timeout=60)
            if res:
                return etree.parse(BytesIO(res.content))
            else:
                return None
        except:
            return None


STATED_IN = 'P248'
GR = 'Q2359213'
RETRIEVED = 'P813'

def make_quals(repo, name, subs):
    quals = []
    quals.append(point_in_time_claim(repo))
    if name:
        named_as_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
        named_as_claim.setTarget(name)
        quals.append(named_as_claim)
    if subs:
        sub_count_claim = pywikibot.Claim(repo, SUB_COUNT, is_qualifier=True)
        sub_count_claim.setTarget(make_quantity(int(subs), repo))
        quals.append(sub_count_claim)
    return quals
    

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/authors.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

GR_AUTH_ID = 'P2963'
NAMED_AS = 'P1810'
SUB_COUNT = 'P3744'

for g in tqdm(generator):
    d = g.get()
    gr_authors = get_valid_claims(d, GR_AUTH_ID)

    for author in gr_authors:
        author_id = author.getTarget()
        if not author_id:
            continue
        gr_author = get_author(author_id)
        if not gr_author:
            continue
        name = gr_author.find("author/name").text
        fans = gr_author.find("author/fans_count").text

        point_in_time = point_in_time_claim(repo)
        quals = make_quals(repo, name, fans)


        update_qualifiers(repo, author, quals, "update goodreads data")


