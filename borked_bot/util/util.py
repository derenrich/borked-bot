import requests
import pywikibot
import datetime

def get_valid_claims(item, prop_id):
    claims = item['claims'].get(prop_id, [])
    return [c for c in claims if c.getRank() != "deprecated"]


def get_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'BorkedBot[Wikidata]'})
    return s

def add_claim(repo, item, prop, target, sources = [], comment=""):
    c = pywikibot.Claim(repo, prop)
    c.setTarget(target)
    item.addClaim(c, summary=comment, bot=True)
    if sources:
        c.addSources(sources, summary="adding sources", bot=True)
    return c

def retrieved_claim(repo):
    today = datetime.date.today()
    now = pywikibot.WbTime(year=today.year, month=today.month, day=today.day)
    retrieved = pywikibot.Claim(repo, u'P813')
    retrieved.setTarget(now)
    return retrieved



