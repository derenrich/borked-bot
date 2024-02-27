from ..credentials import CREDENTIALS
from .util import *
from requests.exceptions import ReadTimeout, ConnectionError

MAX_RESULTS = 100


class TwitchError(Exception): pass


@retry(exceptions=[ConnectionError, ReadTimeout])
def get_twitch_access_token(session):
    # https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#client-credentials-grant-flow
    params = {
        "client_id": CREDENTIALS["twitch-client-id"],
        "client_secret": CREDENTIALS["twitch-secret"],
        "grant_type": "client_credentials",
    }
    r = session.post("https://id.twitch.tv/oauth2/token", data=params)
    r.raise_for_status()
    data = r.json()
    # The response also includes an "expires_in" field, which is the number of seconds
    # the token is valid for. Technically we get penalized if we are frequently calling
    # the API with expired tokens. But from my testing these tokens are good for multiple
    # days at a time, so I won't implement that now.
    return data["access_token"]


@retry(exceptions=[ConnectionError, ReadTimeout])
def create_twitch_session():
    s = get_session()
    s.headers.update({
        "Client-Id": CREDENTIALS["twitch-client-id"],
    })
    token = get_twitch_access_token(s)
    s.headers.update({
        "Client-Id": CREDENTIALS["twitch-client-id"],
        "Authorization": f"Bearer {token}",
    })
    return s


@retry(exceptions=[ConnectionError, ReadTimeout])
def batch_get_twitch_ids(session, handles):
    if len(handles) > MAX_RESULTS:
        raise TwitchError(f"Cannot lookup more than {MAX_RESULTS} handles")
    params = {
        "login": handles, # login=foo&login=bar&login=baz
    }
    r = session.get("https://api.twitch.tv/helix/users", params=params)
    r.raise_for_status()
    data = r.json()
    return {
        user["login"]: user["id"]
        for user in data
    }


@retry(exceptions=[ConnectionError, ReadTimeout])
def get_twitch_follows(session, user_id):
    params = {
        "broadcaster_id": user_id,
    }
    r = session.get("https://api.twitch.tv/helix/channels/followers", params=params)
    r.raise_for_status()
    data = r.json()
    return data["total"]