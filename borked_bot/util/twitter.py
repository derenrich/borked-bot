from ..credentials import CREDENTIALS
from .util import retry
from requests.exceptions import ReadTimeout

ROOT_URL = "https://api.twitter.com/2/users/by"

@retry(exceptions=[ReadTimeout])
def batch_get_twitter(session, handles):
    handles = ','.join(handles)
    params = {}
    params['usernames'] = handles
    params['user.fields'] = 'created_at,verified'

    headers = {}
    headers['Authorization'] = f'Bearer {CREDENTIALS["twitter-bearer"]}'
    
    r = session.get(ROOT_URL, params=params, headers=headers, timeout=10)
    if r:
        res = r.json()
        if 'data' in res:
            out = dict()
            for r in res['data']:
                out[r['username'].lower()] = r
            return out
    return {}
