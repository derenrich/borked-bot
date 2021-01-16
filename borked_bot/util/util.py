import requests
import pywikibot
import datetime
import logging
import time
import sys
from datetime import timezone

MAX_LAG_BACKOFF_SECS = 10 * 60

def get_item(item):
    try:
        return item.get()
    except pywikibot.exceptions.NoPage:
        return None
    except pywikibot.exceptions.UnknownSite:
        return None

def retry(count=3, wait=1, exceptions=[pywikibot.data.api.APIError]):
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


def get_valid_claims(item, prop_id):
    claims = item['claims'].get(prop_id, [])
    return [c for c in claims if c.getRank() != "deprecated"]

def get_valid_qualifier(claim, qual_id):
    return [q for q in claim.qualifiers.get(qual_id, []) if q.getTarget()]

def get_valid_qualifier_values(claim, qual_id):
    return [q.getTarget() for q in claim.qualifiers.get(qual_id, []) if q.getTarget()]

def get_valid_qualifier_times(claim, qual_id):
    return [q.getTarget().toTimestamp() for q in claim.qualifiers.get(qual_id, []) if q.getTarget()]

def get_all_qualifier_values(claim, qual_id):
    return [q.getTarget() for q in claim.qualifiers.get(qual_id, [])]

def get_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'BorkedBot[Wikidata]'})
    return s

def add_claim(repo, item, prop, target, sources = [], qualifiers = [], comment=""):
    try:
        c = pywikibot.Claim(repo, prop)
        c.setTarget(target)
        if qualifiers:
            for qual in qualifiers:
                c.addQualifier(qual)
        item.addClaim(c, summary=comment, bot=True)
        if sources:
            c.addSources(sources, summary="adding sources", bot=True)
        return c
    except (pywikibot.exceptions.OtherPageSaveError, pywikibot.data.api.APIMWException) as ex:
        logging.error("failed to add claim for prop %s", prop, exc_info=ex)
        time.sleep(30)
    except pywikibot.exceptions.MaxlagTimeoutError as ex:
        logging.error("max lag timeout. sleeping. failed to add claim for prop %s", prop, exc_info=ex)
        time.sleep(MAX_LAG_BACKOFF_SECS)

@retry()
def update_qualifiers(repo, claim, qualifiers, comment=""):
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

def retrieved_claim(repo):
    today = datetime.datetime.now(timezone.utc)
    now = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, u'P813')
    retrieved.setTarget(now)
    return retrieved


def point_in_time_claim(repo, time=None):
    today = datetime.datetime.now(timezone.utc)
    now = time or pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, u'P585', is_qualifier=True)
    retrieved.setTarget(now)
    return retrieved


def make_quantity(val, repo):
    return pywikibot.WbQuantity(val, site=repo)

def make_date(year, month, day):
    return pywikibot.WbTime(year=year, month=month, day=day)

