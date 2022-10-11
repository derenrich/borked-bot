import pywikibot
import traceback
import sys
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..util.util import *
from ..util.mediawiki import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime
import random

BALLOTPEDIA_PAGE = 'P2390'

# 1 requests per second
ballotpedia_limiter = RateLimiter(max_calls=60, period=60)

s = get_session()

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/pages.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

MW_PAGE_ID = 'P9675'

count = 0
for item in tqdm(generator):
    d = get_item(item)
    if not d:
        continue

    bp_claims = get_valid_claims(d, BALLOTPEDIA_PAGE)
    if not bp_claims:
        continue

    for bp_claim in bp_claims:
        try:
            bp_string = bp_claim.getTarget()
            if bp_string:
                if get_qualifiers(bp_claim, MW_PAGE_ID):
                    # we almost certainly already visited this item
                    continue
                api_url = "https://ballotpedia.org/wiki/api.php"

                quals = get_wikipage_quals(s, repo, api_url, bp_string)
                if quals:
                    count += 1
                    # don't want language for this
                    quals = [q for q in quals if q.id != 'P407']
                    update_qualifiers(repo, bp_claim, quals, "update metadata from ballotpedia wiki API")
                else:
                    print(f"failed to fetch for {bp_string}")
        except ValueError:
            traceback.print_exception(*sys.exc_info())


print(f"updated {count} entries")


