import requests
import pywikibot
import datetime
import logging
import time

MAX_LAG_BACKOFF_SECS = 10 * 60

def get_valid_claims(item, prop_id):
    claims = item['claims'].get(prop_id, [])
    return [c for c in claims if c.getRank() != "deprecated"]

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

def retrieved_claim(repo):
    today = datetime.date.today()
    now = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, u'P813')
    retrieved.setTarget(now)
    return retrieved



