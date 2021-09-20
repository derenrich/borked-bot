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

FANDOM_PAGE = 'P6262'

# 300 requests per 15-minute window
fandom_limiter = RateLimiter(max_calls=300, period=15 * 60)

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

    fandom_claims = get_valid_claims(d, FANDOM_PAGE)
    if not fandom_claims:
        continue

    for fandom_claim in fandom_claims:
        try:
            fandom_string = fandom_claim.getTarget()
            if fandom_string:
                if get_qualifiers(fandom_claim, MW_PAGE_ID):
                    # we almost certainly already visited this item
                    continue
                fandom_prefix, fandom_article = fandom_string.split(':', 1)
                if '.' in fandom_prefix:
                    lang, fandom_subdomain = fandom_prefix.split('.')
                else:
                    fandom_subdomain = fandom_prefix
                    lang = None
                if fandom_prefix == 'lyrics':
                    continue
                
                api_url = f"https://{fandom_subdomain}.fandom.com/api.php?"
                if lang:
                    api_url = f"https://{fandom_subdomain}.fandom.com/{lang}/api.php?"
                quals = get_wikipage_quals(s, repo, api_url, fandom_article)
                if quals:
                    count += 1
                    update_qualifiers(repo, fandom_claim, quals, "update metadata from fandom API")
                else:
                    # try again on wikia
                    api_url = f"https://{fandom_subdomain}.wikia.com/api.php?"
                    if lang:
                        api_url = f"https://{fandom_subdomain}.wikia.com/{lang}/api.php?"
                    quals = get_wikipage_quals(s, repo, api_url, fandom_article)
                    if quals:
                        count += 1
                        update_qualifiers(repo, fandom_claim, quals, "update metadata from fandom API")
        except ValueError:
            traceback.print_exception(*sys.exc_info())


print(f"updated {count} entries")


