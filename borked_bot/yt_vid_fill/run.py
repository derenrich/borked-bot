import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ..util.youtube import *
from ..util.util import *
from ..util.batcher import *
from tqdm import tqdm
from datetime import datetime
from borked_bot.util.ratelimit import RateLimiter
from dateutil.parser import isoparse
from isodate import parse_duration
import random
import traceback
import sys

# we can do 10k queries per day or one every 0.11 seconds
yt_limiter = RateLimiter(max_calls=11, period=100)
yt = make_yt_client()
session = get_session()

VIEW_COUNT = 'P5436' # statistics.viewCount	
YT_CHAN_ID = 'P2397'
YT_VID_ID = 'P1651'
NAMED_AS = 'P1810' # snippet.title
TITLE = 'P1476'
START_TIME = 'P580' # snippet.publishedAt
PUB_DATE = 'P577'
POINT_IN_TIME = 'P585'
DURATION = 'P2047'
SECONDS = 'Q11574'
MIN_DATA_AGE_DAYS = 60
MAX_YT_PER_REQ = 50
LANG = 'P407'

def make_quals(repo, view_count, title, start_time, lang_qid, iso_duration, channel):
    quals = []
    if title:
        named_as_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
        named_as_claim.setTarget(title.strip())
        quals.append(named_as_claim)
    if view_count and int(view_count) > 0:
        view_count_claim = pywikibot.Claim(repo, VIEW_COUNT, is_qualifier=True)
        view_count_claim.setTarget(make_quantity(int(view_count), repo))
        quals.append(view_count_claim)
    if start_time:
        start_claim = pywikibot.Claim(repo, PUB_DATE, is_qualifier=True)
        start = isoparse(start_time)
        start_claim.setTarget(make_date(start.year, start.month, start.day))
        quals.append(start_claim)
    if lang_qid:
        lang_claim = pywikibot.Claim(repo, LANG, is_qualifier=True)
        LANG_ITEM = pywikibot.ItemPage(repo, lang_qid)
        lang_claim.setTarget(LANG_ITEM)
        quals.append(lang_claim)
    if iso_duration:
        td = parse_duration(iso_duration)
        seconds = td.total_seconds()
        SECONDS_ITEM =  pywikibot.ItemPage(repo, SECONDS)
        seconds_quant = pywikibot.WbQuantity(seconds, site=repo, unit=SECONDS_ITEM)
        dur_claim = pywikibot.Claim(repo, DURATION, is_qualifier=True)
        dur_claim.setTarget(seconds_quant)
        quals.append(dur_claim)
    if channel:
        chan_claim = pywikibot.Claim(repo, YT_CHAN_ID, is_qualifier=True)
        chan_claim.setTarget(channel)
        quals.append(chan_claim)
    quals.append(point_in_time_claim(repo))
    return quals



def all_gen(wikidata_site):
    WD = str(pathlib.Path(__file__).parent.absolute())
    with open(WD + '/vids.rq', 'r') as query_file:
        QUERY = query_file.read()
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator


def fetch_batch(items):
    vids = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        yt_vids = get_valid_claims(d, YT_VID_ID)
        vids += [chan.getTarget() for chan in yt_vids if chan.getTarget()]
        if len(vids) > MAX_YT_PER_REQ:
            # yes this does mean we will drop some on the floor. not optimal...
            random.shuffle(vids)
            vids = vids[0:MAX_YT_PER_REQ]
    with yt_limiter:
        res = batch_list_vids(yt, vids)
    return res

def update_yt_vid(repo, wikidata_site, dry_run=False):
    generator = all_gen(wikidata_site)
    eg_string = editgroup_string()
    count = 0
    for item, fetch in batcher(tqdm(generator), fetch_batch, 40):
        d = get_item(item)
        if not d:
            continue
        yt_chans = get_valid_claims(d, YT_VID_ID)
        
        for yt_vid_claim in yt_chans:
            try:
                yt_vid_id = yt_vid_claim.getTarget()
                points_in_time = get_present_qualifier_values(yt_vid_claim, POINT_IN_TIME)
                if points_in_time:
                    max_time = max(map(lambda t: t.toTimestamp(), points_in_time))
                    if (datetime.now() - max_time).total_seconds() < 24 * 60 * 60 * MIN_DATA_AGE_DAYS:
                        # don't update new data
                        continue
                if yt_vid_id in fetch:
                    data = fetch[yt_vid_id]
                    iso_duration = data.get('contentDetails', {}).get('duration')
                    view_count = data.get('statistics',{}).get('viewCount')
                    title = data.get('snippet',{}).get('title')
                    channel = data.get('snippet',{}).get('channelId')
                    if get_present_qualifier_values(yt_vid_claim, TITLE):
                        # don't update if there's a title already
                        title = None
                    start_time =  data.get('snippet', {}).get('publishedAt')
                    lang = parse_iso_lang(data.get('snippet', {}).get('defaultLanguage')) or parse_iso_lang(data.get('snippet', {}).get('defaultAudioLanguage'))
                    if get_present_qualifier_values(yt_vid_claim, LANG):
                        # don't update if there's a lang already
                        lang = None
                    quals = make_quals(repo, view_count, title, start_time, lang, iso_duration, channel)

                    if dry_run:
                        print(f"dry run: would update youtube video {yt_vid_id} on item {item.title()} with quals {quals}")
                    else:
                        update_qualifiers(repo, yt_vid_claim, quals, "update youtube video data from api " + eg_string)
                    count += 1
                else:
                    pass
            except ValueError:
                print(f"failed to process youtube video {yt_vid_id} on item {item.title()}")
                traceback.print_exception(*sys.exc_info())
    print(f"updated {count} entries")
