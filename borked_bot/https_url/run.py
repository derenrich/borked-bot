import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
from requests.exceptions import ReadTimeout, ConnectionError
from ..util.util import *
from tqdm import tqdm
import urllib3
from string import Template
import typing

HTTPS_PREFIX = "https://"
HTTP_PREFIX = "http://"

def check_upgrade_to_ssl(session: requests.Session, url: str) -> typing.Optional[str]:
    try:
        response = session.get(url, timeout=5)
        new_url = response.url
        status_code = response.status_code
        # are the two URLs the same except for HTTPS
        if status_code == 200 and new_url.startswith(HTTPS_PREFIX) and new_url[len(HTTPS_PREFIX):].strip("/") == url[len(HTTP_PREFIX):].strip("/"):
            return new_url
        else:
            return None
    except (urllib3.exceptions.MaxRetryError, ReadTimeout, ConnectionError, UnicodeError) as e:
        return None

MAX_OFFSET = 1_700_000 # ~ number of valid url items
LIMIT = 100_000

URL_PID = "P856"
s = get_session()

WD = str(pathlib.Path(__file__).parent.absolute())
SPARQL_FILE = "/urls.rq"

with open(WD + SPARQL_FILE, 'r') as query_file:
    QUERY_TEMPLATE = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()


offset = 0
while offset <  MAX_OFFSET:
    query = Template(QUERY_TEMPLATE).substitute(offset=offset, limit=LIMIT)
    generator = pg.WikidataSPARQLPageGenerator(query, site=wikidata_site)
    for item in tqdm(generator):
        d = get_item(item)
        if not d:
            continue

        url_claims = get_valid_claims(d, URL_PID)
        for url_claim in url_claims:
            url_target = url_claim.getTarget()
            if url_target and url_target.startswith(HTTP_PREFIX):
                new_url = check_upgrade_to_ssl(s, url_target)
                if new_url:
                    url_claim.setTarget(new_url)
                    try:
                        item.editEntity(summary="Update URL to HTTPS")
                    except:
                        continue
    offset += LIMIT
    


