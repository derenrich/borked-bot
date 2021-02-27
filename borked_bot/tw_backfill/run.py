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

s = get_session()

VIEW_COUNT = 'P5436' # statistics.viewCount	
TWITTER_USERNAME = 'P2002'
HAS_QUAL = 'P1552'
VERIFIED = 'Q28378282'
TWITTER_ID = 'P6552'
NAMED_AS = 'P1810' # snippet.title	
START_TIME = 'P580' # snippet.publishedAt
END_TIME = 'P582'
POINT_IN_TIME = 'P585'
MIN_DATA_AGE_DAYS = 40
FOLLOWERS = 'P8687'
SUB_COUNT = 'P3744'
POINT_IN_TIME = 'P585'

def make_quals(repo, twt_id, point_in_time):
    quals = []
    if twt_id:
        twt_id_claim = pywikibot.Claim(repo, TWITTER_ID, is_qualifier=True)
        twt_id_claim.setTarget(twt_id)
        quals.append(twt_id_claim)
    quals.append(point_in_time)
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
        tw_ids += map(str, sum([get_present_qualifier_values(t, TWITTER_ID) for t in tw_handles], []))
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
for item in tqdm(generator):

    d = get_item(item)
    if not d:
        continue
    if len(get_valid_claims(d, FOLLOWERS)) > 1:
        update_twitter_sub(d)
        # we already backfilled this
        continue
    twt_handles = get_valid_claims(d, TWITTER_USERNAME)
    twt_ids = list(map(str, sum([get_present_qualifier_values(t, TWITTER_ID) for t in twt_handles], [])))
    if len(twt_ids) != 1:
        # for now ignore this case
        continue
    for twt in twt_handles:
        try:
            counts = get_present_qualifier_values(twt, SUB_COUNT)
            times = get_present_qualifier_values(twt, POINT_IN_TIME)
            if len(counts) != 1 or len(times) != 1:
                continue
            if (datetime.now() - times[0].toTimestamp() ).total_seconds() < 24 * 60 * 60 * MIN_DATA_AGE_DAYS:
                continue
            followers = int(counts[0].amount)
            if followers and followers >= 1000:
                follower_quant = make_quantity(followers, repo)
                quals = make_quals(repo, twt_ids[0], point_in_time_claim(repo, times[0]))
                add_claim(repo, item, FOLLOWERS, follower_quant, qualifiers=quals, comment="backfill follower count")
                count += 1
                update_twitter_sub(d)
                #if count > 10:
                #    exit()
            else:
                pass
        except ValueError:
            traceback.print_exception(*sys.exc_info())
            #exit()

print(f"updated {count} entries")


