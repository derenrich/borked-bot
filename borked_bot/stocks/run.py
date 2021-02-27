import pywikibot
import traceback
import sys
from pywikibot import pagegenerators as pg
import pathlib
from ratelimiter import RateLimiter
from ..credentials import CREDENTIALS
from ..util.util import *
from tqdm import tqdm
from dateutil.parser import isoparse
from datetime import datetime
import random
import json
from requests.exceptions import ReadTimeout

# 5 req / minute
limiter = RateLimiter(max_calls=5, period=65)
polygon_key = CREDENTIALS['polygonio']

s = get_session()

STOCK_EXCHANGE = 'P414'
TICKER = 'P249'
NAMED_AS = 'P1810'
START_TIME = 'P580'
END_TIME = 'P582'
STATED_IN = 'P248'
POLYGON = 'Q105523379'

class ThrottleException(Exception):
    pass

def make_reference(repo, name):
    retrieved = retrieved_claim(repo)
    stated_in_claim = pywikibot.Claim(repo, STATED_IN)
    stated_in_claim.setTarget(pywikibot.ItemPage(repo, POLYGON))
    refs = [stated_in_claim]
    if name:
        named_as_claim = pywikibot.Claim(repo, NAMED_AS)    
        named_as_claim.setTarget(name)
        refs.append(named_as_claim)
    refs.append(retrieved)
    return refs

@retry(6, 1, [ThrottleException, ReadTimeout])
def get_ticker(ticker):
    url = f"https://api.polygon.io/v1/meta/symbols/{ticker}/company?&apiKey={polygon_key}"
    with limiter:
        res = s.get(url)
    if res:
        return res.json()
    elif res.status_code == 429:
        raise ThrottleException()
    return None

def add_sic(repo, item, data, ticker_info):
    SIC_CODE = 'P3242'
    if get_valid_claims(data, SIC_CODE):
        return
    if not ticker_info.get('sic'):
        return
    sic_code = str(ticker_info['sic'])
    name = ticker_info.get('name')
    references = make_reference(repo, name)
    add_claim(repo, item, SIC_CODE, sic_code, references, comment='import SIC code using ticker')

def add_cik(repo, item, data, ticker_info):
    CIK = 'P5531'
    if get_valid_claims(data, CIK):
        return
    if not ticker_info.get('cik'):
        return
    cik_code = str(ticker_info['cik'])
    if len(cik_code) < 10:
        cik_code = '0' * (10 - len(cik_code)) + cik_code
    name = ticker_info.get('name')
    references = make_reference(repo, name)
    add_claim(repo, item, CIK, cik_code, references, comment='import CIK using ticker')

def add_lei(repo, item, data, ticker_info):
    LEI = 'P1278'
    if get_valid_claims(data, LEI):
        return
    if not ticker_info.get('lei'):
        return
    lei_code = str(ticker_info['lei'])
    name = ticker_info.get('name')
    references = make_reference(repo, name)
    add_claim(repo, item, LEI, lei_code, references, comment='import LEI using ticker')

def add_start_time(repo, item, data, ticker_info, exchange):
    if get_valid_qualifier(exchange, START_TIME):
        return
    if not ticker_info.get('listdate'):
        return
    start_date = isoparse(ticker_info.get('listdate'))
    wb_start_date = pywikibot.WbTime(year=start_date.year, month=start_date.month, day=start_date.day)
    start_claim = pywikibot.Claim(repo, START_TIME, is_qualifier=True)
    start_claim.setTarget(wb_start_date)
    update_qualifiers(repo, exchange, [start_claim], comment='import start ticker time')

    name = ticker_info.get('name')
    references = make_reference(repo, name)
    update_sources(exchange, references, "add reference")
    

SUPPORTED_EXCHANGES = set(['Q13677', 'Q82059'])
SUPPORTED_EXCHANGE_SYMBOLS = {'NGS': 'Q82059',
                              'NYE': 'Q13677',
                              'NSC': 'Q82059',
                              'NSD': 'Q82059',
                              'NasdaqGM': 'Q82059',
                              'NYSE': 'Q13677',
                              'NasdaqGS': 'Q82059',
                              'New York Stock Exchange': 'Q13677',
                              'NASDAQ Global Market': 'Q82059',
                              'NasdaqCM': 'Q82059',
                              'NASDAQ Capital Market': 'Q82059',
                              'Nasdaq Global Select': 'Q82059'}



WD = str(pathlib.Path(__file__).parent.absolute())

with open(WD + '/tickers.rq', 'r') as query_file:
    QUERY = query_file.read()

wikidata_site = pywikibot.Site("wikidata", "wikidata")
log_page = pywikibot.Page(wikidata_site, 'User:BorkedBot/StockLogs')
wiki_log = WikiLogger(log_page)
repo = wikidata_site.data_repository()

generator = pg.WikidataSPARQLPageGenerator(QUERY, site=wikidata_site)

count = 0
logs = open('log3.json','wt')
for item in tqdm(generator):

    d = get_item(item)
    if not d:
        continue
    def valid_exchange(c):
        ex = c.getTarget()
        return len(get_valid_qualifier_values(c, TICKER)) == 1 and ex.getID() in SUPPORTED_EXCHANGES
    exchange = get_best_claim(d, STOCK_EXCHANGE, valid_exchange)
    if not exchange:
        continue
    tickers = get_valid_qualifier_values(exchange, TICKER)
    if len(tickers) != 1:
        continue
    
    for ticker in tickers:
        try:
            
            info = get_ticker(ticker)
            if not info:
                wiki_log.append(f"Can't find {ticker} for [[{item.title()}]]")
                continue
            
            json.dump(info, logs)
            logs.write("\n")
            logs.flush()

            if not info.get('active'):
                continue

            if 'exchangeSymbol' not in info and "exchange" not in info:
                print('no exchange?', info, item)
                continue

            exchange_name = info.get('exchangeSymbol') or info.get("exchange")
            if exchange_name not in SUPPORTED_EXCHANGE_SYMBOLS:
                print('unsupported ex', ticker, item, exchange_name)
                continue
            expected_exchange = SUPPORTED_EXCHANGE_SYMBOLS[exchange_name]
            if expected_exchange != exchange.getTarget().getID():
                print('ex mismatch', expected_exchange, exchange)
                wiki_log.append(f"exchange mismatch {ticker} for [[{item.title()}]]")
                continue
            add_sic(repo, item, d, info)
            add_cik(repo, item, d, info)
            add_lei(repo, item, d, info)            
            add_start_time(repo, item, d, info, exchange)
            if count > 100:
                sys.exit()
            #print(info, item)
            #add_claim(repo, item, FOLLOWERS, follower_quant, qualifiers=quals, comment="add follower count")
            count += 1
        except ValueError:
            traceback.print_exception(*sys.exc_info())

print(f"updated {count} entries")

