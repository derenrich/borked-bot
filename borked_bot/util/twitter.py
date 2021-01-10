from ..credentials import CREDENTIALS
from .util import retry
from requests.exceptions import ReadTimeout
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
 
