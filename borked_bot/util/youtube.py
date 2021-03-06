from ..credentials import CREDENTIALS
from .util import *
from googleapiclient.discovery import build

YT_MAX_RESULTS = 50

def make_yt_client():
    api_service_name = "youtube"
    api_version = "v3"
    api_key = CREDENTIALS['youtube']
    
    youtube = build(api_service_name, api_version, developerKey=api_key)
    return youtube

@retry(exceptions=[ConnectionError])
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

@retry(exceptions=[ConnectionError])
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

