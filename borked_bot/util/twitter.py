from ..credentials import CREDENTIALS
#from .util import retry
from .util import *
from requests.exceptions import ReadTimeout
from itertools import groupby
import re

HANDLE_ROOT_URL = "https://api.twitter.com/2/users/by"
ID_ROOT_URL = "https://api.twitter.com/2/users"

USERNAME_REGEX = re.compile(r"^[0-9]{1,19}$")

class TwitterError(Exception): pass

@retry(exceptions=[ReadTimeout, TwitterError])
def batch_get_twitter(session, handles, mode="handles", extra_fields=[]):
    params = {}
    if mode == "handles":
        params['usernames'] = ','.join(handles)
    elif mode == "ids":
        handles = [h for h in handles if USERNAME_REGEX.match(h)]
        params['ids'] = ','.join(handles)
    else:
        raise RuntimeError(f"invalid mode {mode} must be 'handles' or 'ids'")
    params['user.fields'] = ','.join(['created_at,verified'] + extra_fields)

    headers = {}
    headers['Authorization'] = f'Bearer {CREDENTIALS["twitter-bearer"]}'

    root_url = HANDLE_ROOT_URL
    if mode == "ids":
        root_url = ID_ROOT_URL
    r = session.get(root_url, params=params, headers=headers, timeout=10)
    if r:
        res = r.json()
        if 'data' in res:
            out = dict()
            for r in res['data']:
                if mode == 'handles':
                    out[r['username'].lower()] = r
                elif mode == 'ids':
                    out[r['id']] = r
            return out
    else:
        raise TwitterError(f"Twitter API Error: {r.content}")
 

def update_twitter_sub(item):
    FOLLOWERS = 'P8687'
    POINT_IN_TIME = 'P585'
    TWITTER_ID = 'P6552'
    
    follower_claims = get_valid_claims(item, FOLLOWERS)
    twitter_follower_claims = [c for c in follower_claims if len(get_valid_qualifier_values(c, TWITTER_ID)) == 1]
    id_counts = groupby(twitter_follower_claims, lambda c: get_valid_qualifier_values(c, TWITTER_ID)[0])
    for twt_id, claims in id_counts:
        claims = list(claims)
        if len(claims) > 1:
            newest_date = max([max(get_valid_qualifier_times(c, POINT_IN_TIME)) for c in claims])
            for c in claims:
                if max(get_valid_qualifier_times(c, POINT_IN_TIME)) < newest_date:
                    if c.rank != 'normal':
                        c.changeRank('normal')
                else:
                    c.changeRank('preferred')
