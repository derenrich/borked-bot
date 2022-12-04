import pywikibot
import traceback
from pywikibot import pagegenerators as pg
import pathlib
from ..util.util import *
from tqdm import tqdm
import random
from string import Template
import time
import logging


BANNED_REFS = set(['P143','P4656','P813', 'P7569','P9675','P1476','P50', 'P1810'])
DATE_PROP = ['P569', 'P570']
REASON_FOR_UPRANK = 'P7452'
MOST_PRECISE_VALUE = 'Q71536040'

LIMIT = 200
WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/dates.rq', 'r') as query_file:
    QUERY_TEMPLATE = query_file.read()
    
wikidata_site = pywikibot.Site("wikidata", "wikidata")
repo = wikidata_site.data_repository()

def make_qualifier() -> pywikibot.Claim:
    stated_in_claim = pywikibot.Claim(repo, REASON_FOR_UPRANK, is_qualifier = True)
    stated_in_claim.setTarget(pywikibot.ItemPage(repo, MOST_PRECISE_VALUE))
    return stated_in_claim

def get_most_specific(date_claims):
    # sort such that more precise and well cited claims appear later
    date_claims_sorted = sorted(date_claims, key=lambda d: (d.getTarget().precision, is_well_cited(d)))
    most_specific = date_claims_sorted[-1]
    # check that the less specific dates are consistent
    for date in [dc.getTarget() for dc in date_claims_sorted[0:-1]]:
        if date.calendarmodel != most_specific.getTarget().calendarmodel:
            return None
        if date.precision >= 7 and date.year // 100 != most_specific.getTarget().year // 100:
            return None                
        if date.precision >= 8 and date.year // 10 != most_specific.getTarget().year // 10:
            return None        
        if date.precision >= 9 and date.year != most_specific.getTarget().year:
            return None
        if date.precision >= 10 and date.month and date.month != most_specific.getTarget().month:
            return None
        if date.precision >= 11 and date.day and date.day != most_specific.getTarget().day:
            return None
    # now we have a date that's more specific than a bunch of others
    return most_specific

def is_well_cited(date_claim) -> bool:
    sources = date_claim.getSources()
    if not sources:
        return False
    for source in sources:
        for s in source:
            if s not in BANNED_REFS:
                return True
    return False

def main():
    """
    For a random selection of humans find DOB/DOD and update them to the most precise value.
    Only update the most precise value if it has a good reference.
    """
    MAX_OFFSET = 10_100_000 # there are roughly 10MM humans in wikidata
    start_idx = random.randint(0, MAX_OFFSET)
    logger = get_logger(__name__)

    logger.info(f"starting at offset={start_idx}")
    for offset in range(start_idx, MAX_OFFSET, LIMIT):
        logger.info(f"query for offset={offset}")
        QUERY = Template(QUERY_TEMPLATE).substitute(offset=offset, limit=LIMIT)
        time.sleep(2)
        try:
            generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
        except Exception as e:
            logger.error("failed to run SPARQL query", e)
            traceback.print_exc()
            continue
        count = 0
        for item in tqdm(generator):
            d = get_item(item)
            if not d:
                continue

            for dp in DATE_PROP:
                unqualified_date_claims = [c for c in get_valid_claims(d, dp) if not c.qualifiers and c.getTarget()]
                if len(unqualified_date_claims) < 2:
                    # nothing to change
                    continue
                if any([c.getTarget().before for c in unqualified_date_claims] + [c.getTarget().after for c in unqualified_date_claims]):
                    # don't deal with dates with uncertainty for now
                    continue
                if any([c.getRank() == 'preferred' for c in unqualified_date_claims]):
                    # don't touch already preferred claims
                    continue

                best_date_claim = get_most_specific(unqualified_date_claims)
                if best_date_claim:
                    month = best_date_claim.getTarget().month
                    day = best_date_claim.getTarget().day
                    if month == 1 and day == 1:
                        # skip jan1 dates because they are error prone
                        continue
                if best_date_claim and is_well_cited(best_date_claim):
                    count += 1
                    best_date_claim.changeRank('preferred')
                    best_date_claim.addQualifier(make_qualifier())

        logger.info(f"updated {count} entries")

