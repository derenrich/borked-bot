import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from ..util.reddit import *
from tqdm import tqdm
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import prawcore
import sys

SUBREDDIT_ID = 'P3984'
END_TIME = 'P582'
HAS_QUALITY = 'P1552'
PRIVATE_SUBREDDIT = 'Q72970624'
NAMED_AS = 'P1810'
START_TIME = 'P580'
LANGUAGE = 'P407'
FOLLOWERS = 'P8687'
OVER_18 = 'Q83807365'

MIN_SUB_COUNT = 10000
MIN_AGE_DAYS = timedelta(days=365)

WD = str(pathlib.Path(__file__).parent.absolute())
with open(WD + '/subreddits.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
reddit = make_reddit_client()


def mark_subreddit_as_dead(claim):
    point_in_time = point_in_time_claim(repo)
    end_claim = pywikibot.Claim(repo, END_TIME, is_qualifier=True)
    end_claim.setSnakType('somevalue')
    update_qualifiers(repo, claim, [point_in_time, end_claim], "marking subreddit as dead")

def mark_subreddit_as_private(claim):
    point_in_time = point_in_time_claim(repo)
    private_claim = pywikibot.Claim(repo, HAS_QUALITY, is_qualifier=True)
    target = pywikibot.ItemPage(repo, PRIVATE_SUBREDDIT)
    private_claim.setTarget(target)
    update_qualifiers(repo, claim, [private_claim, point_in_time], "marking subreddit as private")



def add_subreddit_subcount(item, d, subreddit_name, sub_count):
    subreddit_name = subreddit_name.lower()
    age = claim_age(d, FOLLOWERS, SUBREDDIT_ID, subreddit_name)
    if age > MIN_AGE_DAYS and sub_count > MIN_SUB_COUNT:
        # need to update the subreddit count
        follower_quant = make_quantity(sub_count, repo)
        quals = []
        quals.append(point_in_time_claim(repo))
        sr_claim = pywikibot.Claim(repo, SUBREDDIT_ID, is_qualifier=True)
        sr_claim.setTarget(subreddit_name)
        quals.append(sr_claim)
        add_claim(repo, item, FOLLOWERS, follower_quant, qualifiers=quals, comment="add reddit sub count", rank='preferred')
        update_most_recent_rank(d, FOLLOWERS, SUBREDDIT_ID)
    
    
def add_subreddit_qualifiers(claim, s):
    point_in_time = point_in_time_claim(repo)

    name = s.title
    name_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
    name_claim.setTarget(name.strip())

    subreddit_type = s.subreddit_type

    lang = s.lang
    lang_qid = parse_iso_lang(lang)
    lang_claim = None
    if lang_qid:
        lang_claim = pywikibot.Claim(repo, LANGUAGE, is_qualifier=True)
        lang_target = pywikibot.ItemPage(repo, lang_qid)
        lang_claim.setTarget(lang_target)

    over18 = s.over18
    over18_claim = None
    if over18:
        over18_claim = pywikibot.Claim(repo, HAS_QUALITY, is_qualifier=True)
        over18_qid = pywikibot.ItemPage(repo, OVER_18)
        over18_claim.setTarget(over18_qid)
    created_at = s.created_utc
    created_at_date = datetime.utcfromtimestamp(created_at)
    created_at_wb = make_date(created_at_date.year, created_at_date.month, created_at_date.day)
    created_at_claim = pywikibot.Claim(repo, START_TIME, is_qualifier=True)
    created_at_claim.setTarget(created_at_wb)


    qualifiers = [name_claim, created_at_claim]
    if lang_claim:
        qualifiers.append(lang_claim)
    qualifiers += [point_in_time]
    if over18_claim:
        qualifiers.append(over18_claim)
    
    update_qualifiers(repo, claim, qualifiers, "update subreddit data")
    
for item in tqdm(generator):
    d = get_item(item)
    if not d:
        continue
    subreddits = get_valid_claims(d, SUBREDDIT_ID)
    
    for sr in subreddits:
        sr_name = sr.getTarget()
        if not sr_name:
            continue
        if get_valid_qualifier(sr, END_TIME):
            continue
        s = reddit.subreddit(sr_name)
        try:
            sub_count = s.subscribers
            add_subreddit_qualifiers(sr, s)
            add_subreddit_subcount(item, d, sr_name, sub_count)
        except prawcore.exceptions.NotFound:
            # subreddit doesn't exist anymore
            mark_subreddit_as_dead(sr)
            continue
        except prawcore.exceptions.Redirect:
            # subreddit doesn't exist (maybe never did?)
            mark_subreddit_as_dead(sr)
            continue
        except prawcore.exceptions.Forbidden:
            mark_subreddit_as_private(sr)
            continue

        

