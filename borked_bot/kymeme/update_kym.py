
# Migrate P6760 to P13484

import pywikibot
import traceback
from pywikibot import pagegenerators as pg
import pathlib
from ..util.util import *
from tqdm import tqdm
from dateutil.parser import isoparse
import requests
from bs4 import BeautifulSoup
import urllib.parse

KYM_ID = 'P6760'
KYM_SLUG = 'P13484'
STATED_IN = 'P248'
SUBJECT_NAMED_AS = 'P1810'
HAS_CHAR = 'P1552'
KYM = 'Q2071334'

KYM_QUALS = dict(
    SENSITIVE = 'Q85521961',
    CONFIRMED = 'Q116763038',
    REJECTED = 'Q116763045',
    RESEARCHING = 'Q116763049',
    WARNING = 'Q134120619',
    COVID = 'Q134124721',
    OFFENSIVE = 'Q136091526',
)


def make_reference(repo):
    retrieved = retrieved_claim(repo)
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    stated_in_claim.setTarget(pywikibot.ItemPage(repo, KYM))
    return [retrieved, stated_in_claim]

def get_uncertainty(sub_count):
    # based on https://support.google.com/youtube/answer/6051134
    sub_count_len = len(str(int(sub_count)))
    if sub_count_len < 3:
        return 0
    else:
        return 10 ** (sub_count_len - 3)

def make_quals(repo, kym_id=None, name=None, chars=[]):
    quals = []
    if kym_id:
        id_claim = pywikibot.Claim(repo, KYM_ID, is_qualifier=True)
        id_claim.setTarget(kym_id)
        quals.append(id_claim)
    if name:
        name_claim = pywikibot.Claim(repo, SUBJECT_NAMED_AS, is_qualifier=True)
        name_claim.setTarget(name)
        quals.append(name_claim)
    if chars:
        for char in chars:
            char_item = pywikibot.ItemPage(repo, char)
            char_claim = pywikibot.Claim(repo, HAS_CHAR, is_qualifier=True)
            char_claim.setTarget(char_item)
            quals.append(char_claim)
    quals.append(point_in_time_claim(repo))
    return quals


def read_sparql_file(filename):
    WD = str(pathlib.Path(__file__).parent.absolute())
    with open(WD + '/' + filename, 'r') as query_file:
        return query_file.read()


def all_gen(wikidata_site) -> pg.WikidataSPARQLPageGenerator:
    QUERY = read_sparql_file('query.rq')
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator


def migrate_kymeme(repo, wikidata_site, dry_run=False):
    eg_string = editgroup_string()
    s = get_session()

    for item in all_gen(wikidata_site):
        assert isinstance(item, pywikibot.ItemPage)
        time.sleep(0.1)  # be nice to the server
        d = get_item(item)
        if not d:
            continue
        kym_claim: pywikibot.Claim = get_best_claim(d, KYM_ID)

        # kym will redirect to the slug page if it's valid
        if not kym_claim or not kym_claim.getTarget():
            continue
        kym_id = kym_claim.getTarget()
        resp = s.get(f"https://knowyourmeme.com/memes/{kym_id}")
        if resp.status_code != 200:
            print(f"Skipping invalid KYMeme ID {kym_id} on item {item.title()}")
            continue
        resp.raise_for_status()


        slug = resp.url.split('/')[-1]
        # url decode the slug
        slug = urllib.parse.unquote(slug)
        
        # the name of the meme is in $(".entry-title").text() so we get that
        soup = BeautifulSoup(resp.text, 'html.parser')
        name = soup.select_one(".entry-title").text.strip()

        kym_slug_claim = get_best_claim(d, KYM_SLUG)  
        if kym_slug_claim:
            print(f"KYMeme slug already exists on item {item.title()}, skipping...")
            continue

        # characteristic data are in a dl inside the tag aside
        dl = soup.select_one("aside.left dl")
        # extract dd values as strings
        dds = [dd.text.strip() for dd in dl.select("dd")]
        chars = []
        for dd in dds:
            if dd.startswith("Confirmed"):
                chars.append(KYM_QUALS['CONFIRMED'])
            elif dd.startswith("Sensitive"):
                chars.append(KYM_QUALS['SENSITIVE'])
            elif dd.startswith("Deadpool"):
                chars.append(KYM_QUALS['REJECTED'])
            elif dd.startswith("Submission"):
                chars.append(KYM_QUALS['RESEARCHING'])
            elif dd.startswith("Warning"):
                chars.append(KYM_QUALS['WARNING'])
            elif dd.startswith("COVID-19"):
                chars.append(KYM_QUALS['COVID'])

        ref = make_reference(repo)
        quals = make_quals(repo, kym_id=kym_id, name=name, chars=chars)
        if not dry_run:
            # add the new claim
            add_claim(repo, item, KYM_SLUG, slug, sources=ref, qualifiers=quals, comment="migrate kym " + eg_string)
            # remove the old claim
            item.removeClaims(kym_claim, summary="removing old kym id " + eg_string, bot=True)
        else:
            print("dry run mode, not saving changes", item.title(), kym_id, slug, quals, ref)
        print(f"Migrating KYMeme ID {kym_id} on item {item.title()} to slug {slug}")

