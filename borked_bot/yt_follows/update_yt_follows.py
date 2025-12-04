import pywikibot
import traceback
import sys, os, math
from pywikibot import pagegenerators as pg
import pathlib
from ..util.ratelimit import RateLimiter
from ..util.util import *
from ..util.youtube import *
from ..util.batcher import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime, date, timedelta

# we can do 10k queries per day or one every 0.11 seconds
yt_limiter = RateLimiter(max_calls=11, period=100)

USERS_PER_REQ = 75

s = get_session()

MIN_VIEWS = 250_000
MIN_FOLLOWS = 5_000
MAX_YT_PER_REQ = 50
YT_CHAN_ID = 'P2397'
YT_HANDLE_ID = 'P11245'
YT_API_ID = 'Q8056784'
FOLLOWERS = 'P8687'
VIEWS = 'P5436'
STATED_IN = 'P248'
DETERMINATION_METHOD = 'P459'
YT_VIEW_COUNT_METHOD = 'Q63185508'


def make_reference(repo):
    retrieved = retrieved_claim(repo)
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    stated_in_claim.setTarget(pywikibot.ItemPage(repo, YT_API_ID))
    return [retrieved, stated_in_claim]

def get_uncertainty(sub_count):
    # based on https://support.google.com/youtube/answer/6051134
    sub_count_len = len(str(int(sub_count)))
    if sub_count_len < 3:
        return 0
    else:
        return 10 ** (sub_count_len - 3)

def make_quals(repo, yt_id, handle=None):
    quals = []
    if yt_id:
        yt_id_claim = pywikibot.Claim(repo, YT_CHAN_ID, is_qualifier=True)
        yt_id_claim.setTarget(yt_id)
        quals.append(yt_id_claim)
    if handle:
        yt_handle_claim = pywikibot.Claim(repo, YT_HANDLE_ID, is_qualifier=True)
        yt_handle_claim.setTarget(handle)
        quals.append(yt_handle_claim)
    quals.append(point_in_time_claim(repo))
    return quals


def read_sparql_file(filename):
    WD = str(pathlib.Path(__file__).parent.absolute())
    with open(WD + '/' + filename, 'r') as query_file:
        return query_file.read()

def fixed_gen(wikidata_site, qid):
    item = pywikibot.ItemPage(wikidata_site, qid)
    yield item

def enwiki_gen(wikidata_site):
    QUERY = read_sparql_file('accounts_all_enwiki.rq')
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator

def all_gen(wikidata_site):
    QUERY = read_sparql_file('accounts_all.rq')
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator

def template_gen(wikidata_site, template_title):
    template = pywikibot.Page(wikidata_site, template_title)
    for enwiki_page in template.getReferences(only_template_inclusion=True):
        if enwiki_page.namespace() != 0:
            continue
        item = pywikibot.ItemPage.fromPage(enwiki_page, lazy_load=True)
        if item is not None:
            yield item

def should_update_enwiki(old_sub_count, new_sub_count):
    if old_sub_count is None:
        return True
    if old_sub_count * 1.1 < new_sub_count :
        # did the yt chan grow by 10%?
        return True
    if int(math.log10(old_sub_count)) < int(math.log10(new_sub_count)):
        # did the yt chan cross a power of 10 threshold?
        return True
    return False


def fetcher(min_age_days=365):
    """
    Returns a function that fetches YouTube channel data for a batch of items,
    ensuring that the wikidata data is at least `min_age_days` old before actually fetching.
    """
    def fetch(items):
        return fetch_batch(items, min_data_age_days=min_age_days)
    return fetch

def fetch_batch(items, min_data_age_days=365):
    yt_client = make_yt_client()
    yt_ids = []
    for item in items:
        d = get_item(item)
        if not d:
            continue
        yt_chans = get_valid_claims(d, YT_CHAN_ID)
        new_yt_ids = [chan.getTarget() for chan in yt_chans if chan.getTarget()]
        for yt_id in new_yt_ids:
            age = claim_age(d, FOLLOWERS, YT_CHAN_ID, yt_id)
            if (age.days >= min_data_age_days):
                yt_ids.append(yt_id)
    def get_batch_yt(yt_ids):
        with yt_limiter:
            res = batch_list_chan(yt_client, yt_ids)
        return res
    res = {}
    results = batcher(yt_ids, get_batch_yt, MAX_YT_PER_REQ)
    for _, fetch in results:
        res.update(dict(fetch))
    return res

def try_set_handle(repo, item, d, handle, yt_id, dry_run=False, eg_string=""):
    # check if we already have a handle claim for this handle
    existing_handles = get_valid_claims(d, YT_HANDLE_ID)
    if existing_handles:
        for eh in existing_handles:
            if eh.getTarget() and eh.getTarget().lower() == handle.lower():
                if dry_run:
                    print(f"would skip adding handle {handle} to {item.title()} because it already exists")
                return
    if dry_run:
        print(f"would add handle {handle} to {item.title()}")
    else:
        ref = make_reference(repo)
        add_claim(repo, item, YT_HANDLE_ID, handle, sources=ref, qualifiers=make_quals(repo, yt_id), comment="add missing YouTube handle " + eg_string, rank='normal')


def try_update_view_count(repo, item, d, view_count, yt_id, handle, dry_run=False, eg_string=""):
    # check if we already have a view count claim for this yt id
    newest_claim = latest_claim(d, VIEWS, YT_CHAN_ID, yt_id)   
    if newest_claim is not None:
        old_view_count = get_target_float_quantity(newest_claim)
        view_count_age = date.today() - get_point_in_time(newest_claim)
    else:
        old_view_count = None
        view_count_age = timedelta(days=9999)

    if should_update_enwiki(old_view_count, view_count) or view_count_age >= timedelta(days=365):
        view_quant = make_quantity(view_count, repo)
        ref = make_reference(repo)
        quals = make_quals(repo, yt_id, handle)

        yt_det = pywikibot.Claim(repo, DETERMINATION_METHOD, is_qualifier=True)
        yt_det.setTarget(pywikibot.ItemPage(repo,YT_VIEW_COUNT_METHOD))
        quals.append(yt_det)
        if dry_run:
            print(f"would add view count {view_count} to {item.title()} for yt id {yt_id}")
        else:
            add_claim(repo, item, VIEWS, view_quant, sources=ref, qualifiers=quals, comment="add YouTube view count " + eg_string, rank='normal')
            update_most_recent_rank(d, VIEWS, YT_CHAN_ID)
    elif dry_run:
        print(f"would skip adding view count {view_count} to {item.title()} for yt id {yt_id} because old was {old_view_count} and age was {view_count_age.days} days")


def update_yt_subs(repo, item_generator, should_update_func, COMMENT_ADDENDUM="", min_age_days=365, dry_run=False, only_best: bool=True):
    eg_string = editgroup_string()
    for item, fetch in tqdm(batcher(item_generator, fetcher(min_age_days), USERS_PER_REQ, shuffle=False)):
        d = get_item(item)
        if not d:
            continue

        yt_claims = []
        if only_best:
            yt_claim = get_best_claim(d, YT_CHAN_ID)
            if not yt_claim:
                continue
            yt_claims.append(yt_claim)
        else:
            yt_claims = get_valid_claims(d, YT_CHAN_ID)

        for yt_claim in yt_claims:
            yt_id = yt_claim.getTarget()
            if not yt_id:
                continue
            try:
                if yt_id in fetch:
                    data = fetch[yt_id]

                    handle = data.get('snippet', {}).get('customUrl')
                    if handle:
                        handle = handle.lstrip('@')
                        try_set_handle(repo, item, d, handle, yt_id, dry_run=dry_run, eg_string=eg_string)

                    view_count = data.get('statistics', {}).get('viewCount')
                    if view_count is not None and int(view_count) >= MIN_VIEWS:
                        view_count = int(view_count)
                        try_update_view_count(repo, item, d, view_count, yt_id, handle, dry_run=dry_run, eg_string=eg_string)

                    sub_count = data.get('statistics', {}).get('subscriberCount')
                    if sub_count is None or int(sub_count) < MIN_FOLLOWS:
                        continue
                    sub_count = int(sub_count)

                    newest_claim = latest_claim(d, FOLLOWERS, YT_CHAN_ID, yt_id)
                    old_sub_count = get_target_float_quantity(newest_claim)


                    # are there not enough new subs?
                    should_we_update_subs = should_update_func(old_sub_count, sub_count)
                    if newest_claim:
                        # we automatically update if the data is older than a year
                        should_we_update_date =  date.today() - get_point_in_time(newest_claim) >= timedelta(days=365)
                    else:
                        should_we_update_date = True

                    if not should_we_update_subs and not should_we_update_date:
                        if dry_run:
                            print(f"would skip {item.title()} with {old_sub_count} old and {sub_count} new subs")
                        continue

                    if dry_run:
                        print(f"would add {sub_count} followers to {item.title()}", should_we_update_date, should_we_update_subs, old_sub_count, sub_count)
                    else:
                        uncertainty = get_uncertainty(sub_count)
                        follower_quant = make_quantity(sub_count, repo, error=(uncertainty - 1, 0))
                        quals = make_quals(repo, yt_id, handle)
                        ref = make_reference(repo)
                        add_claim(repo, item, FOLLOWERS, follower_quant, sources=ref, qualifiers=quals, comment="add subscriber count "+ COMMENT_ADDENDUM + " " + eg_string, rank='preferred')
                        update_most_recent_rank(d, FOLLOWERS, YT_CHAN_ID)
            except ValueError:
                traceback.print_exception(*sys.exc_info())

