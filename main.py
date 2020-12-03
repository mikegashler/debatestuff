from typing import List, Mapping, Dict, Any, cast, Tuple
import webserver
import urllib.parse
import ast
import session
import feed
import account
import rec
from db import db
import sys
import os

def do_index(query: Mapping[str, Any], session_id: str) -> str:
    return f'<html><head><meta http-equiv="refresh" content="0;URL=\'feed.html\'"></head></html>'

if __name__ == "__main__":
    db.load()
    webserver.SimpleWebServer.render({
        'index.html': do_index,
        'feed.html': feed.do_feed,
        'feed_ajax.html': feed.do_ajax,
        'account.html': account.do_account,
        'account_ajax.html': account.do_ajax,
        'receive_image.html': account.receive_image,
    })
    db.save()
    print('\nGoodbye.')
