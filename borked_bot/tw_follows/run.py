import pywikibot
import traceback
import sys
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from ..util.twitter import *
from ..util.batcher import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime
import random

# 300 requests per 15-minute window
twt_limiter = RateLimiter(max_calls=300, period=15 * 60)

# Up to 100 are allowed in a single request
MAX_USERS_PER_REQ = 100
USERS_PER_REQ = 75

s = get_session()

NUMBER_OF_WORKS = 'P3740' # statistics.videoCount	
NUMBER_OF_FOLLOWERS = 'P3744' # statistics.subscriberCount	
VIEW_COUNT = 'P5436' # statistics.viewCount	
TWITTER_USERNAME = 'P2002'
HAS_QUAL = 'P1552'
VERIFIED = 'Q28378282'
TWITTER_ID = 'P6552'
NAMED_AS = 'P1810' # snippet.title	
START_TIME = 'P580' # snippet.publishedAt
END_TIME = 'P582'
POINT_IN_TIME = 'P585'
MIN_DATA_AGE_DAYS = 14
MAX_YT_PER_REQ = 50
FOLLOWERS = 'P8687'

def make_quals(repo, twt_id):
    quals = []
    if twt_id:
        twt_id_claim = pywikibot.Claim(repo, TWITTER_ID, is_qualifier=True)
        twt_id_claim.setTarget(twt_id)
        quals.append(twt_id_claim)
    quals.append(point_in_time_claim(repo))
    return quals

WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/accounts.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

def fetch_batch(items):
    tw_ids = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        tw_handles = get_valid_claims(d, TWITTER_USERNAME)
        tw_ids += map(str, sum([get_valid_qualifier_values(t, TWITTER_ID) for t in tw_handles], []))
    def get_batch_handles(handles):
        with twt_limiter:
            res = batch_get_twitter(s, handles, mode='ids', extra_fields=['public_metrics'])
        return res
    res = {}
    results = batcher(tw_ids, get_batch_handles, MAX_USERS_PER_REQ)
    for _, fetch in results:
        res.update(dict(fetch))
    return res

count = 0
for item, fetch in batcher(tqdm(generator), fetch_batch, USERS_PER_REQ):
    d = get_item(item)
    if not d:
        continue

    twt_claim = get_best_claim(d, TWITTER_USERNAME)
    if not twt_claim:
        continue
    twt_ids = get_valid_qualifier_values(twt_claim, TWITTER_ID)
    if len(twt_ids) != 1:
        continue
    for twt_id in twt_ids:
        try:
            if twt_id in fetch:
                data = fetch[twt_id]
                followers = data.get('public_metrics', {}).get('followers_count')
                if followers and followers >= 10000:
                    follower_quant = make_quantity(followers, repo)
                    quals = make_quals(repo, twt_id)
                    add_claim(repo, item, FOLLOWERS, follower_quant, qualifiers=quals, comment="add follower count")
                    count += 1
        except ValueError:
            traceback.print_exception(*sys.exc_info())

print(f"updated {count} entries")


