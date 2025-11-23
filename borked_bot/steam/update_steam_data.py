import pywikibot
from pywikibot import pagegenerators as pg
import pathlib
import requests

from borked_bot.util.ratelimit import RateLimiter
from .api import get_steam_app_details, SteamAppData
from ..util.youtube import *
from ..util.util import *
from ..util.batcher import *
from tqdm import tqdm
from lxml import etree
from io import StringIO, BytesIO
from datetime import datetime
from dateutil.parser import isoparse
import random
import traceback
import sys


def all_gen(wikidata_site):
    WD = str(pathlib.Path(__file__).parent.absolute())

    with open(WD + '/query.rq', 'r') as query_file:
        QUERY = query_file.read()
    generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)
    return generator


def update_steam_data(repo, wikidata_site, dry_run=False):
    session = get_session()
    eg_string = editgroup_string()

    count = 0
    for item in tqdm(all_gen(wikidata_site), desc="processing steam data updates"):
        time.sleep(.3)
        d = get_item(item)
        print(d)
        if not d:
            continue

        steam_apps = get_valid_claims(d, 'P1733')  # Steam App ID

        for steam_app in steam_apps:
            try:
                appid = steam_app.getTarget().strip()

                if not appid.isdigit():
                    continue

                app_data = get_steam_app_details(int(appid), session)
                if not app_data:
                    continue
                print(app_data)
                # Process app_data as needed and update Wikidata item d

            except Exception as e:
                print(f"Error processing item {item.title()}: {e}")
                traceback.print_exc()
