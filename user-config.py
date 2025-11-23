# -*- coding: utf-8 -*-

import os
import dotenv as _dotenv

_dotenv.load_dotenv()

family = 'wikidata'
mylang = 'wikidata'
usernames['wikidata']['wikidata'] = 'BorkedBot'
usernames['wikipedia']['en'] = 'BorkedBot'
usernames['commons']['commons'] = 'BorkedBot'


console_encoding = 'utf-8'
maxlag = 5
max_retries = 1000
maxthrottle = 120
put_throttle = 3
socket_timeout = 240

user_agent_description = "maintainer: BrokenSegue"


_CONSUMER_TOKEN = os.environ['CONSUMER_TOKEN']
_CONSUMER_SECRET = os.environ['CONSUMER_SECRET']
_ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
_ACCESS_TOKEN_SECRET = os.environ['ACCESS_TOKEN_SECRET']

authenticate['*.wikipedia.org'] = authenticate['*.wikimedia.org'] =  authenticate['*.wikidata.org'] = (_CONSUMER_TOKEN, _CONSUMER_SECRET, _ACCESS_TOKEN, _ACCESS_TOKEN_SECRET)
