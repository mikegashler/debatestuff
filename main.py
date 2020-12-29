from typing import List, Mapping, Dict, Any, cast, Tuple
import webserver
import urllib.parse
import ast
import sessions
import feed
import accounts
import sessions
import rec
from db import db
import sys
import os
import posts
from config import config

def do_index(query: Mapping[str, Any], session_id: str) -> str:
    return f'<html><head><meta http-equiv="refresh" content="0;URL=\'feed.html\'"></head></html>'

def bootstrap_recursive(id: str, par_id: str, ob: Mapping[str, Any], account_ids: Dict[Any, str], sess: sessions.Session) -> None:
    if 'account' in ob:
        key = ob['account']
        if key in account_ids:
            account_id = account_ids[key]
        else:
            acc = accounts.make_starter_account()
            account_id = acc.id
            account_ids[key] = account_id
            sess.account_ids.append(account_id)
    else:
        account_id = ''
    posts.new_post(id, par_id, ob['type'], ob['text'], account_id)
    if 'children' in ob:
        for child in ob['children']:
            bootstrap_recursive(posts.new_post_id(), id, child, account_ids, sess)

# Populate the database with some initial data.
# This is only called the first time, when the database is empty.
def bootstrap() -> None:
    # The next client to connect will be given admin privileges
    sess: sessions.Session = sessions.reserve_session()
    sess.active_account().admin = True

    # Populate the comment tree
    root_id = '000000000000'
    account_ids: Dict[Any, str] = {}
    if 'bootstrap' in config:
        # Bootstrap with data from config
        bs = cast(Mapping[str, Any], config['bootstrap'])
        bootstrap_recursive(root_id, '', bs, account_ids, sess)
    else:
        # No bootstrap data, so just do a bare bones setup.
        posts.new_post(root_id, '', 'cat', 'Everything', '')
    sessions.session_cache.set_modified(sess.id)

if __name__ == "__main__":
    db.load()
    if db.have_no_accounts():
        bootstrap()
    webserver.SimpleWebServer.render({
        'index.html': do_index,
        'feed.html': feed.do_feed,
        'feed_ajax.html': feed.do_ajax,
        'accounts.html': accounts.do_account,
        'account_ajax.html': accounts.do_ajax,
        'receive_image.html': accounts.receive_image,
    })
    db.save()
    print('\nGoodbye.')
