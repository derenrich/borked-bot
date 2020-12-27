import pywikibot
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
POINT_IN_TIME = 'P585'
MIN_DATA_AGE_DAYS = 14
MAX_YT_PER_REQ = 50

def make_quals(repo, twt_id, verified, start_time):
    quals = []
    if twt_id:
        twt_id_claim = pywikibot.Claim(repo, TWITTER_ID, is_qualifier=True)
        twt_id_claim.setTarget(twt_id)
        quals.append(twt_id_claim)
    if verified:
        verified_claim = pywikibot.Claim(repo, HAS_QUAL, is_qualifier=True)
        VERIFIED_ITEM = pywikibot.ItemPage(repo, VERIFIED)
        verified_claim.setTarget(VERIFIED_ITEM)
        quals.append(verified_claim)
    if start_time:
        start_claim = pywikibot.Claim(repo, START_TIME, is_qualifier=True)
        start = isoparse(start_time)
        start_claim.setTarget(make_date(start.year, start.month, start.day))
        quals.append(start_claim)
    quals.append(point_in_time_claim(repo))        
    return quals


WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/handles.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

def fetch_batch(items):
    handles = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        tw_handles = get_valid_claims(d, TWITTER_USERNAME)
        handles += [tw.getTarget() for tw in tw_handles if tw.getTarget()]
    if len(handles) > MAX_USERS_PER_REQ:
        # yes this does mean we will drop some on the floor. not optimal...
        random.shuffle(handles)
        handles = handles[0:MAX_USERS_PER_REQ]
    with twt_limiter:
        res = batch_get_twitter(s, handles)
    return res

count = 0
for item, fetch in batcher(tqdm(generator), fetch_batch, USERS_PER_REQ):
    d = get_item(item)
    if not d:
        continue
    twt_handles = get_valid_claims(d, TWITTER_USERNAME)    
    for twt_handle_claim in twt_handles:
        twt_handle = twt_handle_claim.getTarget().lower()
        points_in_time = get_valid_qualifier_values(twt_handle_claim, POINT_IN_TIME)
        if points_in_time:
            max_time = max(map(lambda t: t.toTimestamp(), points_in_time))
            if (datetime.now() - max_time).total_seconds() < 24 * 60 * 60 * MIN_DATA_AGE_DAYS:
                # don't update new data
                continue
        if twt_handle in fetch:
            data = fetch[twt_handle]
            start_time = data.get('created_at')
            twt_id = data.get('id')
            verified = data.get('verified')
            quals = make_quals(repo, twt_id, verified, start_time)
            
            update_qualifiers(repo, twt_handle_claim, quals, "update twitter data")
            count += 1
        else:
            pass
print(f"updated {count} entries")


