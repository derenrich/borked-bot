import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..util.youtube import *
from ..credentials import CREDENTIALS
from ..util.util import *
from ..util.batcher import *
from tqdm import tqdm
import isbnlib
from lxml import etree
from io import StringIO, BytesIO
from datetime import datetime
from dateutil.parser import isoparse
import random
import traceback
import sys

# we can do 10k queries per day or one every 0.11 seconds
yt_limiter = RateLimiter(max_calls=11, period=100)
yt = make_yt_client()
session = get_session()

NUMBER_OF_WORKS = 'P3740' # statistics.videoCount	
NUMBER_OF_FOLLOWERS = 'P3744' # statistics.subscriberCount	
VIEW_COUNT = 'P5436' # statistics.viewCount	
YT_CHAN_ID = 'P2397'
NAMED_AS = 'P1810' # snippet.title	
START_TIME = 'P580' # snippet.publishedAt
POINT_IN_TIME = 'P585'
MIN_DATA_AGE_DAYS = 60
MAX_YT_PER_REQ = 50

def make_quals(repo, video_count, sub_count, view_count, title, start_time):
    quals = []
    if title:
        named_as_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
        named_as_claim.setTarget(title.strip())
        quals.append(named_as_claim)
    if sub_count and int(sub_count) > 0:
        sub_count_claim = pywikibot.Claim(repo, NUMBER_OF_FOLLOWERS, is_qualifier=True)
        sub_count_claim.setTarget(make_quantity(int(sub_count), repo))
        quals.append(sub_count_claim)
    if video_count and int(video_count) > 0:
        video_count_claim = pywikibot.Claim(repo, NUMBER_OF_WORKS, is_qualifier=True)
        video_count_claim.setTarget(make_quantity(int(video_count), repo))
        quals.append(video_count_claim)
    if view_count and int(view_count) > 0:
        view_count_claim = pywikibot.Claim(repo, VIEW_COUNT, is_qualifier=True)
        view_count_claim.setTarget(make_quantity(int(view_count), repo))
        quals.append(view_count_claim)
    if start_time:
        start_claim = pywikibot.Claim(repo, START_TIME, is_qualifier=True)
        start = isoparse(start_time)
        start_claim.setTarget(make_date(start.year, start.month, start.day))
        quals.append(start_claim)
    quals.append(point_in_time_claim(repo))        
    return quals


WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/chans.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

def fetch_batch(items):
    chans = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        yt_chans = get_valid_claims(d, YT_CHAN_ID)
        chans += [chan.getTarget() for chan in yt_chans if chan.getTarget()]
        if len(chans) > MAX_YT_PER_REQ:
            # yes this does mean we will drop some on the floor. not optimal...
            random.shuffle(chans)
            chans = chans[0:MAX_YT_PER_REQ]
    with yt_limiter:
        res = batch_list_chan(yt, chans)
    return res


count = 0
for item, fetch in batcher(tqdm(generator), fetch_batch, 40):
    d = get_item(item)
    if not d:
        continue
    yt_chans = get_valid_claims(d, YT_CHAN_ID)
    
    for yt_chan_claim in yt_chans:
        try:
            yt_chan_id = yt_chan_claim.getTarget()
            points_in_time = get_present_qualifier_values(yt_chan_claim, POINT_IN_TIME)
            if points_in_time:
                max_time = max(map(lambda t: t.toTimestamp(), points_in_time))
                if (datetime.now() - max_time).total_seconds() < 24 * 60 * 60 * MIN_DATA_AGE_DAYS:
                    # don't update new data
                    continue
            if yt_chan_id in fetch:
                data = fetch[yt_chan_id]
                # TODO: detect autogen channels (as in https://www.wikidata.org/w/index.php?title=Q7405619&diff=prev&oldid=1316612455)
                video_count = data.get('statistics', {}).get('videoCount')
                sub_count = data.get('statistics', {}).get('subscriberCount')
                view_count = data.get('statistics',{}).get('viewCount')
                title = data.get('snippet',{}).get('title')
                start_time =  data.get('snippet', {}).get('publishedAt')
                quals = make_quals(repo, video_count, sub_count, view_count, title, start_time)
                update_qualifiers(repo, yt_chan_claim, quals, "update youtube data")
                count += 1
            else:
                pass
        except ValueError:
            traceback.print_exception(*sys.exc_info())
print(f"updated {count} entries")


