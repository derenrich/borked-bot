import pywikibot
from pywikibot import pagegenerators as pg
import pathlib

from ..util.youtube import *
from ..util.util import *
from ..util.batcher import *
from tqdm import tqdm
from io import StringIO, BytesIO
from datetime import datetime
from dateutil.parser import isoparse
import random
import traceback
import sys

BSKY_HANDLE = 'P12361'
BSKY_DID = 'P12409'

def make_quals(repo, did):
    quals = []
    did_claim = pywikibot.Claim(repo, BSKY_DID, is_qualifier=True)
    did_claim.setTarget(did.strip())
    quals.append(did_claim)
    quals.append(point_in_time_claim(repo))        
    return quals


def all_gen(wikidata_site):
    WD = str(pathlib.Path(__file__).parent.absolute())

    with open(WD + '/query.rq', 'r') as query_file:
        QUERY = query_file.read()
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator



def update_bsky_did(repo, wikidata_site, dry_run=False):
    session = get_session()
    eg_string = editgroup_string()

    count = 0
    for item in tqdm(all_gen(wikidata_site), desc="processing bsky did updates"):
        time.sleep(.3)
        d = get_item(item)
        if not d:
            continue
        bskys = get_valid_claims(d, BSKY_HANDLE)
        
        for bsky in bskys:
            try:
                bsky_handle = bsky.getTarget()

                if not bsky_handle:
                    continue

                resp = session.get(f"https://api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={bsky_handle}")
                if resp.status_code != 200:
                    continue

                data = resp.json()
                did = data.get('did')
                if not did:
                    print(f"Warning: No DID found for {bsky_handle} on item {item.title()}")
                    continue

                if dry_run:
                    print(f"would update {item.title()} bsky handle {bsky_handle} to did {did}")
                else:
                    quals = make_quals(repo, did)
                    update_qualifiers(repo, bsky, quals, "update bsky did " + eg_string)
                    count += 1
            except ValueError:
                traceback.print_exception(*sys.exc_info())
    print(f"updated {count} entries")


