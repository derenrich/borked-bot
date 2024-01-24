from ..credentials import CREDENTIALS
from .util import *
from googleapiclient.discovery import build
import socket
from requests.exceptions import ReadTimeout, ConnectionError
#from bs4 import BeautifulSoup

YT_MAX_RESULTS = 50

def make_yt_client():
    api_service_name = "youtube"
    api_version = "v3"
    api_key = CREDENTIALS['youtube']
    
    youtube = build(api_service_name, api_version, developerKey=api_key)
    return youtube

@retry(exceptions=[ConnectionError, socket.timeout])
def batch_list_chan(yt, ids):
    grouped_ids = ','.join(ids)
    req = yt.channels().list(part="contentDetails,statistics,snippet,status,brandingSettings",
                             maxResults=YT_MAX_RESULTS,
                             id=grouped_ids)
    res = req.execute()
    out = dict()

    if 'items' not in res:
        return out

    for c in res['items']:
        out[c['id']] = c
    return out

@retry(exceptions=[ConnectionError, socket.timeout])
def batch_list_vids(yt, ids):
    grouped_ids = ','.join(ids)
    req = yt.videos().list(part="contentDetails,statistics,snippet,status",
                             maxResults=YT_MAX_RESULTS,
                             id=grouped_ids)
    res = req.execute()
    out = dict()

    if 'items' not in res:
        return out

    for c in res['items']:
        out[c['id']] = c
    return out


@retry(exceptions=[ReadTimeout])
def get_chan_id(session, handle):
    URL = f"https://www.youtube.com/@{handle}"
    response = session.get(URL)
    soup = BeautifulSoup(response, 'html.parser',
                         from_encoding=response.info().get_param('charset'))    
    if soup.findAll("meta", attrs={"itemprop": "channelId"}):
        channelId = soup.find("meta", attrs={
            "itemprop": "channelId"}).get("content")
        return channelId
