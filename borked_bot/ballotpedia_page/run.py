import pywikibot
import traceback
import sys
from pywikibot import pagegenerators as pg
import pathlib
from ..util.util import *
from ..util.mediawiki import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime
import random

BALLOTPEDIA_PAGE = 'P2390'
MW_PAGE_ID = 'P9675'


def all_gen(wikidata_site):
    WD = str(pathlib.Path(__file__).parent.absolute())

    with open(WD + '/pages.rq', 'r') as query_file:
        QUERY = query_file.read()


    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator



def update_ballotpedia_data(repo, wikidata_site, dry_run=False):
    s = get_session()
    eg_string = editgroup_string()
    generator = all_gen(wikidata_site)
    count = 0
    for item in tqdm(generator):
        d = get_item(item)
        if not d:
            continue

        bp_claims = get_valid_claims(d, BALLOTPEDIA_PAGE)
        if not bp_claims:
            continue

        for bp_claim in bp_claims:
            try:
                bp_string = bp_claim.getTarget()
                if bp_string:
                    if get_qualifiers(bp_claim, MW_PAGE_ID):
                        # we almost certainly already visited this item
                        continue
                    api_url = "https://ballotpedia.org/wiki/api.php"

                    quals = get_wikipage_quals(s, repo, api_url, bp_string)
                    if quals:
                        count += 1
                        # don't want language for this
                        quals = [q for q in quals if q.id != 'P407']
                        if not dry_run:
                            update_qualifiers(repo, bp_claim, quals, "update metadata from ballotpedia wiki API " + eg_string)
                        else:
                            print(f"dry run: would update qualifiers for {bp_string} on item {item.title()}")
                    else:
                        print(f"failed to fetch for {bp_string} on item {item.title()}")
            except ValueError:
                traceback.print_exception(*sys.exc_info())


    print(f"updated {count} entries")
