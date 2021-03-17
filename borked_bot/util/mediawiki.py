
import requests
from .util import *
from requests.exceptions import ReadTimeout
from dateutil.parser import isoparse
import pywikibot

NAMED_AS = "P1810"
LANG = 'P407'
LAST_UPDATE = 'P5017'

@retry(exceptions=[ReadTimeout])
def get_wikipage_quals(session, repo, API_ENDPOINT, title):
    payload = {'action':'query', 'titles': title, 'prop': 'info', 'format': 'json'}
    response = session.get(API_ENDPOINT, params=payload)
    if not response:
        return
    response_json = response.json()

    pages = response_json.get('query', {}).get('pages', {})

    for p in pages.values():
        if "missing" in p:
            return
        title = p.get('title')
        lang_code = p.get('pagelanguage')
        touched = p.get('touched')

        quals = []

        if title:
            name_claim = pywikibot.Claim(repo, NAMED_AS, is_qualifier=True)
            name_claim.setTarget(title)
            quals.append(name_claim)
        if lang_code:
            lang_claim = pywikibot.Claim(repo, LANG, is_qualifier=True)
            lang_qid = parse_iso_lang(lang_code)
            if lang_qid:
                LANG_ITEM = pywikibot.ItemPage(repo, lang_qid)
                lang_claim.setTarget(LANG_ITEM)
                quals.append(lang_claim)           

        return quals
