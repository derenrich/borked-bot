
import requests
from .util import *
from requests.exceptions import ReadTimeout, ConnectionError
from dateutil.parser import isoparse
import pywikibot
import urllib3

NAMED_AS = "P1810"
LANG = 'P407'
LAST_UPDATE = 'P5017'
CURID = 'P9675'

@retry(exceptions=[ReadTimeout])
def get_wikipage_quals(session, repo, API_ENDPOINT, title):
    payload = {'action':'query', 'titles': title, 'prop': 'info', 'format': 'json'}
    try:
      response = session.get(API_ENDPOINT, params=payload)
    except (urllib3.exceptions.MaxRetryError, ConnectionError) as e:
      response = None
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
        curid = p.get('pageid')

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
        if curid:
            curid_claim = pywikibot.Claim(repo, CURID, is_qualifier=True)
            curid_claim.setTarget(str(curid))
            quals.append(curid_claim)

        return quals
