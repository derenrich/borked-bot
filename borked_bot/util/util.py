import requests
import pywikibot
import datetime
import logging
import time
import sys
import random
import typing
from datetime import timezone
from collections import defaultdict

MAX_LAG_BACKOFF_SECS = 10 * 60

def editgroup_string() -> str:
    group_id = "{:x}".format(random.randrange(0, 2**48))
    return f"([[:toolforge:editgroups/b/CB/{group_id}|details]])"

def get_item(item: pywikibot.ItemPage):
    try:
        return item.get()
    except pywikibot.exceptions.NoPageError:
        return None
    except pywikibot.exceptions.IsRedirectPageError:
        return None
    except pywikibot.exceptions.UnknownSiteError:
        return None

def retry(count=3, wait=1, exceptions=[pywikibot.exceptions.APIError]):
    def retrier(f):
        def wrapped_f(*args, retry_count = 0, **kwargs):
            try:
                return f(*args, **kwargs)
            except:
                excp_type, excp_val, _ = sys.exc_info()
                if retry_count >= count:
                    raise excp_val
                for e in exceptions:
                    if issubclass(excp_type, e):
                        logging.error(f"Failed attempt {retry_count}, retrying: {excp_type} {excp_val}")
                        time.sleep(wait)
                        return wrapped_f(*args, **kwargs, retry_count=retry_count+1)
                raise excp_val
        return wrapped_f
    return retrier

def get_valid_claims(item: pywikibot.ItemPage | dict, prop_id) -> typing.List[pywikibot.Claim]:
    claims = item['claims'].get(prop_id, []) # type: ignore
    return [c for c in claims if c.getRank() != "deprecated" and not claim_is_ended(c)]

def get_matching_claim(item: pywikibot.ItemPage, prop_id: str, prop_value: typing.Optional[pywikibot.Claim], qualifiers: typing.Dict[str, typing.Any]) -> typing.Optional[pywikibot.Claim]:
    claims = get_valid_claims(item, prop_id)

    for c in claims:
        if prop_value:
            if c.getTarget() !=  prop_value:
                continue
        match = True
        for qp_id, q_value in qualifiers.items():
            q_values = get_valid_qualifier_values(c, qp_id)
            if q_value not in q_values:
                match = False
                break
        if match:
            return c

            
def get_qualifiers(claim, qual_id):
    return [q for q in claim.qualifiers.get(qual_id, [])]

def get_valid_qualifier(claim, qual_id):
    snak_values = set(['somevalue'])
    return [q for q in claim.qualifiers.get(qual_id, []) if q.getTarget() or q.getSnakType() in snak_values]

def get_valid_qualifier_values(claim, qual_id):
    return [q.getTarget() for q in get_valid_qualifier(claim, qual_id)]

def get_present_qualifier_values(claim, qual_id):
    return [q.getTarget() for q in get_valid_qualifier(claim, qual_id) if q.getTarget()]

def get_all_qualifier_values(claim, qual_id):
    return [q.getTarget() for q in claim.qualifiers.get(qual_id, [])]

def get_valid_qualifier_times(claim, qual_id):
    return [q.getTarget().toTimestamp() for q in get_valid_qualifier(claim, qual_id) if q.getTarget()]

def get_best_claim(item, prop_id, consider=lambda c: True) -> typing.Optional[pywikibot.Claim]:
    """
    returns a singular best claim if it exists
    """
    claims = item['claims'].get(prop_id, [])
    best = None
    rank = None
    matched_rank = False
    for c in claims:
        # not deprecated and no end time
        claim_rank = c.getRank()
        if claim_rank != "deprecated" and not claim_is_ended(c) and consider(c):
            if claim_rank == rank:
                matched_rank = True
            elif claim_rank == 'preferred':
                best = c
                rank = claim_rank
                matched_rank = False
            elif not rank:
                best = c
                rank = claim_rank
    if best and not matched_rank:
        return best
    return None

END_QUALS = ['P582', 'P8554', 'P1534']
def claim_is_ended(claim: pywikibot.Claim) -> bool:
    for end_qual in END_QUALS:
        if get_valid_qualifier(claim, end_qual):
            return True
    return False

def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({'User-Agent': 'BorkedBot[Wikidata]'})
    return s



def get_logger(name) -> logging.Logger:
    logging.basicConfig(level = logging.WARN)
    logger = logging.getLogger(name)
    logger.setLevel("INFO")
    return logger

def add_claim(repo, item: pywikibot.ItemPage, prop, target, sources = [], qualifiers = [], comment="", rank='normal'):
    try:
        c = pywikibot.Claim(repo, prop, rank=rank)
        c.setTarget(target)
        if qualifiers:
            for qual in qualifiers:
                c.addQualifier(qual)
        item.addClaim(c, summary=comment, bot=True)
        if sources:
            c.addSources(sources, summary=comment + " (adding sources)", bot=True)
        return c
    except (pywikibot.exceptions.OtherPageSaveError, pywikibot.exceptions.APIError) as ex:
        logging.error("failed to add claim for prop %s", prop, exc_info=ex)
        time.sleep(30)
    except pywikibot.exceptions.MaxlagTimeoutError as ex:
        logging.error("max lag timeout. sleeping. failed to add claim for prop %s", prop, exc_info=ex)
        time.sleep(MAX_LAG_BACKOFF_SECS)

def update_sources(claim, new_sources, comment=""):
    if not new_sources:
        return
    cur_sources = claim.getSources()

    update = True

    BANNED_PID = set(['P585', 'P813']) # no time stuff
    wanted_source_props = set([c.getID() for c in new_sources if c.getID() not in BANNED_PID])
    wanted_source_targets = set([c.getTarget() for c in new_sources if c.getID() not in BANNED_PID])
    for source_claims in cur_sources:
        present_source_props = set([c for c in source_claims if c not in BANNED_PID])
        present_source_targets = set([c.getTarget() for c in sum([v for (c, v) in source_claims.items() if c not in BANNED_PID],[])])
        if present_source_props >= wanted_source_props and present_source_targets >= wanted_source_targets:
            update = False
    if update:
        claim.addSources(new_sources, summary="adding sources", bot=True)


@retry()
def update_qualifiers(repo, claim: pywikibot.Claim, qualifiers, comment=""):
    for q in qualifiers:
        if not q.isQualifier:
            raise Exception("only qualifiers can be passed here")
    props = set([q.getID() for q in qualifiers])
    if len(props) != len(qualifiers):
        raise Exception("added qualifiers must have unique property types")
    # eliminate duplicate quals
    qualifiers = [q for q in qualifiers if not claim.has_qualifier(q.getID(), q.getTarget())]
    props = set([q.getID() for q in qualifiers])

    if len(props) == 1 and list(props)[0] == 'P585':
        # never bother to just update point in time properties
        return

    removed_quals = []
    for p in props:
        removed_quals += claim.qualifiers.get(p, [])
    claim.removeQualifiers(removed_quals, summary="Removing old qualifiers before update")

    for q in qualifiers:
        claim.addQualifier(q, summary=comment)

def retrieved_claim(repo, qualifier=False):
    today = datetime.datetime.now(timezone.utc)
    now = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, u'P813', is_qualifier=qualifier)
    retrieved.setTarget(now)
    return retrieved


def point_in_time_claim(repo, time=None, prop=None):
    today = time or datetime.datetime.now(timezone.utc)
    now = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, prop or u'P585', is_qualifier=True)
    retrieved.setTarget(now)
    return retrieved


def get_target_float_quantity(claim):
    """
    Try to get a float out of the value of a claim
    """
    if claim is None:
        return None
    target = claim.getTarget()
    if target is None:
        return None
    amount = target.amount
    if amount is None:
        return None
    return float(amount)

def make_quantity(val, repo, error=None):
    return pywikibot.WbQuantity(val, site=repo, error=error)

def make_date(year, month, day):
    return pywikibot.WbTime(year=year, month=month, day=day)



LANGS = {
    'bg': 'Q7918',
    'de': 'Q188',
    'en': 'Q1860',
    'en-US': 'Q1860',
    'en-UK': 'Q1860',
    'es': 'Q1321',
    'it': 'Q652',
    'eo': 'Q143',
    'fr': 'Q150',
    'ja': 'Q5287',
    'pl': 'Q809',
    'pt': 'Q5146',
    'ro': 'Q7913',
    'ru': 'Q7737',
    'sv': 'Q9027',
    'nl': 'Q7411',
    'cs': 'Q9056',
    'ca': 'Q7026',
    'sr': 'Q9299',
    'he': 'Q9288',
    'zh': 'Q7850',
    'ko': 'Q9176',
    'zxx': 'Q22282939'
}

def parse_iso_lang(lang):
    return LANGS.get(lang)


class WikiLogger(object):

    def __init__(self, page):
        # site = pywikibot.Site('en', 'wikipedia')
        # page = pywikibot.Page(site, 'Wikipedia:Sandbox')
        self._page = page
        self._text = self._page.get(True)
    def append(self, line):
        self._text = self._text + f"\n*{line}"
        self._page.text = self._text
        self._page.save('appending log line')


POINT_IN_TIME = 'P585'

def claim_age(item, prop_id, qual_id, qual_value):
    """
    how old is the newest point in time for this property/qualifier/value triple
    """
    today = datetime.date.today()
    claims = get_valid_claims(item, prop_id)
    valid_claims = [c for c in claims if qual_value in get_valid_qualifier_values(c, qual_id)]
    if valid_claims:
        points_in_time = list(map(get_point_in_time, valid_claims))
        if points_in_time:
            max_date = max(points_in_time)
            return today - max_date
        else:
            # failed to parse the date
            return datetime.timedelta(days=3652058)
    else:
        return datetime.timedelta(days=3652058)

def latest_claim(item, prop_id, qual_id, qual_value):
    """
    what is the most recent value for this property/qualifier/value triple
    """
    claims = get_valid_claims(item, prop_id)
    valid_claims = [c for c in claims if qual_value in get_valid_qualifier_values(c, qual_id)]
    latest_claim = None
    latest_claim_time = datetime.date.min
    for claim in valid_claims:
        claim_date = get_point_in_time(claim)
        if claim_date is not None and claim_date > latest_claim_time:
            latest_claim = claim
            latest_claim_time = claim_date
    return latest_claim

def wb_time_to_date(wb_time):
    day = wb_time.day
    if wb_time.year > 10000:
        return None
    if day == 0:
        day = 1
    month = wb_time.month
    if month == 0:
        month = 1
    return datetime.date(wb_time.year, month, day)

def get_point_in_time(claim):
    times = get_valid_qualifier_values(claim, POINT_IN_TIME)
    if len(times) >= 2 or not times:
        return datetime.date.min
    time = wb_time_to_date(times[0])
    if time:
        return time
    else:
        return datetime.date.min

def update_most_recent_rank(item, prop_id, qual_id):
    """
    For a property find all statements with a given qualifier value.
    Take the newest statement and make it preferred
    Make all the rest normal rank.
    """
    claims = get_valid_claims(item, prop_id)
    grouped_claims = defaultdict(list)
    for c in claims:
        qual_value = get_valid_qualifier_values(c, qual_id)
        if len(qual_value) >= 2:
            # no idea what we should do. just bail out.
            return
        if qual_value:
            grouped_claims[qual_value[0]].append(c)

    for qual_value, claims in grouped_claims.items():
        claims.sort(key=lambda c: get_point_in_time(c))
        *olders, most_recent = claims
        if not olders:
            # if there's only one don't change rank
            return
        for c in olders:
            if c.getRank() == 'preferred':
                c.changeRank('normal')
        if most_recent.getRank() != 'preferred':
            most_recent.changeRank('preferred')


def ask_sparql(session, prop, value):
    # WARNING: WIP (Not tested)
    headers = dict(Accept="application/sparql-results+json")
    URL = "https://query.wikidata.org/sparql?query=ASK { ?channel wdt:{prop} \"{value}\". }"
    res = session.get(URL, headers=headers).json()
    return res['boolean']
