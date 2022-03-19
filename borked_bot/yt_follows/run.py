import pywikibot
import traceback
import sys, os, math
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from ..util.youtube import *
from ..util.batcher import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime

# we can do 10k queries per day or one every 0.11 seconds
yt_limiter = RateLimiter(max_calls=11, period=100)
yt = make_yt_client()
session = get_session()


USERS_PER_REQ = 75

s = get_session()

MIN_FOLLOWS = 5000
MIN_DATA_AGE_DAYS = 365
MAX_YT_PER_REQ = 50
YT_CHAN_ID = 'P2397'
FOLLOWERS = 'P8687'

def get_uncertainty(sub_count):
    # based on https://support.google.com/youtube/answer/6051134
    sub_count_len = len(str(int(sub_count)))
    if sub_count_len < 3:
        return 0
    else:
        return 10 ** (sub_count_len - 3)

def make_quals(repo, yt_id):
    quals = []
    if yt_id:
        yt_id_claim = pywikibot.Claim(repo, YT_CHAN_ID, is_qualifier=True)
        yt_id_claim.setTarget(yt_id)
        quals.append(yt_id_claim)
    quals.append(point_in_time_claim(repo))
    return quals

def should_update(old_sub_count, new_sub_count):
    if 'ENWIKI' in os.environ:
        if old_sub_count is None:
            return True
        if old_sub_count * 1.1 < new_sub_count :
            # did the yt chan grow by 10%?
            return True
        if int(math.log10(old_sub_count)) < int(math.log10(new_sub_count)):
            # did the yt chan cross a power of 10 threshold?
            return True
        return False
    else:
        return True

SPARQL_FILE = 'accounts.rq'
if 'ALL_ITEMS' in os.environ:
    SPARQL_FILE = 'accounts_all.rq'
if 'ENWIKI' in os.environ:
    SPARQL_FILE = 'accounts_all_enwiki.rq'
    MIN_DATA_AGE_DAYS = 7

WD = str(pathlib.Path(__file__).parent.absolute())
with open(WD + '/' + SPARQL_FILE, 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

def fetch_batch(items):
    yt_ids = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        yt_chans = get_valid_claims(d, YT_CHAN_ID)
        new_yt_ids = [chan.getTarget() for chan in yt_chans if chan.getTarget()]
        for yt_id in new_yt_ids:
            age = claim_age(d, FOLLOWERS, YT_CHAN_ID, yt_id)
            if age.days >= MIN_DATA_AGE_DAYS:
                yt_ids.append(yt_id)
    def get_batch_yt(yt_ids):
        with yt_limiter:
            res = batch_list_chan(yt, yt_ids)
        return res
    res = {}
    results = batcher(yt_ids, get_batch_yt, MAX_YT_PER_REQ)
    for _, fetch in results:
        res.update(dict(fetch))
    return res

count = 0
for item, fetch in batcher(tqdm(generator), fetch_batch, USERS_PER_REQ):
    d = get_item(item)
    if not d:
        continue

    yt_claim = get_best_claim(d, YT_CHAN_ID)
    if not yt_claim:
        continue
    yt_id = yt_claim.getTarget()
    if not yt_id:
        continue
    try:
        if yt_id in fetch:
            data = fetch[yt_id]
            sub_count = data.get('statistics', {}).get('subscriberCount')
            if sub_count is None or int(sub_count) < MIN_FOLLOWS:
                continue
            sub_count = int(sub_count)

            old_sub_count = get_target_float_quantity(latest_claim(d, FOLLOWERS, YT_CHAN_ID, yt_id))
            if  old_sub_count is not None and not should_update(old_sub_count, sub_count):
                continue

            uncertainty = get_uncertainty(sub_count)
            follower_quant = make_quantity(sub_count, repo, error=(uncertainty - 1, 0))
            quals = make_quals(repo, yt_id)
            add_claim(repo, item, FOLLOWERS, follower_quant, qualifiers=quals, comment="add subscriber count", rank='preferred')
            count += 1
            update_most_recent_rank(d, FOLLOWERS, YT_CHAN_ID)
    except ValueError:
        traceback.print_exception(*sys.exc_info())

print(f"updated {count} entries")
