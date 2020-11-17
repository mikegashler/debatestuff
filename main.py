from typing import List, Mapping, Dict, Any, cast, Tuple
import webserver
import urllib.parse
import json
import ast
import session
import feed
import account
import rec
import os

def save_state() -> None:
    packet = {
        'sessions': { s:session.sessions[s].marshal() for s in session.sessions },
        'tree': feed.root.marshal(),
        'engine': rec.engine.marshal(),
    }

    # Write to file
    blob = bytes(json.dumps(packet), 'utf8')
    with open('state.json', mode='wb+') as file:
        file.write(blob)

def load_state() -> None:
    if not os.path.exists('state.json'):
        print('\nNo \'state.json\' file was found, so creating an empty tree.')
        root = feed.id_to_node('')
        feed.Node(root, {'type':'cat', 'title':'Politics', 'descr':'A place for political debates'}, None, None)
        feed.Node(root, {'type':'cat', 'title':'STEM', 'descr':'Debates about science, technology, engineering, math'}, None, None)
        feed.Node(root, {'type':'cat', 'title':'Entertainment', 'descr':'Debates about movies, books, and celebrities'}, None, None)
        feed.Node(root, {'type':'cat', 'title':'Theology', 'descr':'Religion, God, morality, origins, and purpose'}, None, None)
        feed.Node(root, {'type':'cat', 'title':'Miscellaneous', 'descr':'Any debate that does not fit elsewhere'}, None, None)
    else:
        # Parse the file
        blob = None
        with open('state.json', mode='rb') as file:
            blob = file.read()
        packet = json.loads(blob)

        # Load the sessions
        sess_dict = packet['sessions']
        session.sessions = { s:session.Session.unmarshal(sess_dict[s]) for s in sess_dict }

        # Load the node tree
        feed.root = feed.Node.unmarshal(packet['tree']) # assumes the accounts have already been loaded

        # Load the recommender engine
        rec.engine.unmarshal(packet['engine'])

def do_index(query: Mapping[str, Any], session_id: str) -> str:
    return f'<html><head><meta http-equiv="refresh" content="0;URL=\'feed.html\'"></head></html>'

if __name__ == "__main__":
    # feed.bootstrap_tree()
    load_state()
    webserver.SimpleWebServer.render({
        'index.html': do_index,
        'feed.html': feed.do_feed,
        'feed_ajax.html': feed.do_ajax,
        'account.html': account.do_account,
        'account_ajax.html': account.do_ajax,
        'receive_image.html': account.receive_image,
    })
    save_state()
    print('\nGoodbye.')
