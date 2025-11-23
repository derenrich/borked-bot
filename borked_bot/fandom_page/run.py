import pywikibot
import traceback
import sys
from pywikibot import LexemeSense, pagegenerators as pg
import pathlib
from ..util.util import *
from ..util.mediawiki import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime
import random

FANDOM_PAGE = 'P6262'
MW_PAGE_ID = 'P9675'


s = get_session()


def all_gen(wikidata_site):
    WD = str(pathlib.Path(__file__).parent.absolute())

    with open(WD + '/pages.rq', 'r') as query_file:
        QUERY = query_file.read()

    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator


def update_fandom_data(repo, wikidata_site, dry_run=False):
    generator = all_gen(wikidata_site)
    s = get_session()
    eg_string = editgroup_string()
    count = 0
    for item in tqdm(generator):
        if isinstance(item, LexemeSense):
            continue
        d = get_item(item)
        if not d:
            continue

        fandom_claims = get_valid_claims(d, FANDOM_PAGE)
        if not fandom_claims:
            continue

        for fandom_claim in fandom_claims:
            try:
                fandom_string = fandom_claim.getTarget()
                if fandom_string:
                    if get_qualifiers(fandom_claim, MW_PAGE_ID):
                        # we almost certainly already visited this item
                        continue
                    if ':' not in fandom_string:
                        print(f"invalid fandom string {fandom_string} on item {item.title()}")
                        continue
                    fandom_prefix, fandom_article = fandom_string.split(':', 1)
                    if '.' in fandom_prefix:
                        lang, fandom_subdomain = fandom_prefix.split('.')
                    else:
                        fandom_subdomain = fandom_prefix
                        lang = None
                    if fandom_prefix == 'lyrics':
                        continue
                    
                    api_url = f"https://{fandom_subdomain}.fandom.com/api.php?"
                    if lang:
                        api_url = f"https://{fandom_subdomain}.fandom.com/{lang}/api.php?"
                    quals = get_wikipage_quals(s, repo, api_url, fandom_article)
                    if quals:
                        count += 1
                        if not dry_run:
                            update_qualifiers(repo, fandom_claim, quals, "update metadata from fandom API " + eg_string)
                        else:
                            print(f"dry run: would update qualifiers for {fandom_string} on item {item.title()}")
                    else:
                        # try again on wikia
                        api_url = f"https://{fandom_subdomain}.wikia.com/api.php?"
                        if lang:
                            api_url = f"https://{fandom_subdomain}.wikia.com/{lang}/api.php?"
                        quals = get_wikipage_quals(s, repo, api_url, fandom_article)
                        if quals:
                            count += 1
                            if not dry_run:
                                update_qualifiers(repo, fandom_claim, quals, "update metadata from fandom API " + eg_string)
                            else:
                                print(f"dry run: would update qualifiers for {fandom_string} on item {item.title()}")
            except ValueError:
                print(f"failed to process {fandom_string} on item {item.title()}")
                traceback.print_exception(*sys.exc_info())


    print(f"updated {count} entries")


