from typing import List, Mapping, Dict, Any, cast, Tuple, Optional
import webserver
import urllib.parse
import json
import session
import random
import rec
import os

# Load the feed page
if not os.path.exists('feed.html'):
    os.chdir('/home/mike/bin/debate/')
with open('feed.html') as f:
    lines = f.readlines()
    feed_page = ''.join(lines)

class Node():
    # data is stuff the client will see
    # meta is stuff the client will not see
    def __init__(self, parent:Optional['Node'], data:Mapping[str, Any], meta:Optional[Mapping[str,Any]], account: Optional[session.Account]) -> None:
        self.data = data
        self.meta = meta
        self.account = account
        self.children: List['Node'] = []

        # Insert self into tree
        if parent is None:
            self.id = ''
            self.parent = None
        else:
            # Ensure that we're not screwing up the tree by adding the wrong type of child
            if data['type'] == 'rp':
                assert parent.data['type'] == 'rp' or parent.data['type'] == 'pod'
            elif data['type'] == 'pod':
                assert parent.data['type'] == 'op'
            elif data['type'] == 'op':
                assert parent.data['type'] == 'cat'
            elif data['type'] == 'cat':
                assert parent.data['type'] == 'cat'

            # Make my ID
            if len(parent.id) == 0:
                self.id = f'{len(parent.children)}'
            else:
                self.id = f'{parent.id}.{len(parent.children)}'

            # Insert self into tree
            parent.children.append(self)
            self.parent = parent

        # History
        if data['type'] == 'op':
            self.history: List[Mapping[str, Any]] = []
        elif parent is not None and parent.data['type'] != 'cat':
            # Add self to the OP's history
            op = parent
            while op.data['type'] != 'op':
                op = op.parent # type: ignore
            assert op is not None
            op.history.append({
                'act': 'add',
                'node': self,
            })

        # Ratings
        self.ratings: Optional[List[int]] = None
        self.rating_count = 0

    def marshal(self) -> Mapping[str, Any]:
        packet: Dict[str, Any] = {
            'id': self.id,
            'data': self.data,
            'meta': self.meta,
            'ac': None if self.account is None else self.account.id,
            'ch': [ x.marshal() for x in self.children ],
        }
        # There is no need to marshal the history because a suitable history will be reconstructed when the tree is unmarshalled
        return packet

    @staticmethod
    def unmarshal(ob:Mapping[str, Any], parent:Optional['Node']=None) -> 'Node':
        account = None if ob['ac'] is None else session.find_account_by_id(ob['ac'])
        node = Node(parent, ob['data'], ob['meta'], account)
        assert node.id == ob['id'], 'Something got out of sync'
        for c in ob['ch']:
            Node.unmarshal(c, node)
        return node

    # Returns a list of nodes in ancestral order from root to self
    def stack(self) -> List['Node']:
        s: List['Node'] = []
        n = self
        while n is not None:
            s.append(n)
            n = n.parent # type: ignore
        s.reverse()
        return s

    # Rates this node
    def rate(self, ratings: List[float]) -> None:
        if self.ratings is None:
            self.ratings = [ 0 for _ in rec.rating_choices ]
        assert self.ratings is not None
        for i in range(len(ratings)):
            assert ratings[i] >= 0. and ratings[i] <= 1., 'rating out of range'
            self.ratings[i] += max(0, min(1, int(ratings[i])))
        self.rating_count += 1

root = Node(None, {'type':'cat', 'title':'Everything', 'descr':'The root of all categories'}, None, None)

def id_to_node_recursive(tree: Node, id: str) -> Node:
    if len(id) == 0:
        return tree
    per = id.find('.')
    if per < 0:
        per = len(id)
    index = int(id[:per])
    return id_to_node_recursive(tree.children[index], id[per+1:])

# Finds the node with the specified id. (todo: would a dict be faster?)
def id_to_node(id: str) -> Node:
    return id_to_node_recursive(root, id)

def encode_node_for_client(node: Node, account: session.Account) -> Dict[str, Any]:
    # Give the node content to the client
    outgoing_packet: Dict[str, Any] = {
        'act': 'add',
        'id': node.id,
        'data': node.data,
    }

    # Give the client the author's picture and name
    if node.account is not None:
        outgoing_packet['image'] = node.account.image
        outgoing_packet['name'] = node.account.name

    # Tell the client about any relevant whitelist
    if node.parent is not None:
        whitelist: Optional[List[str]] = None
        if node.data['type'] == 'pod' and node.meta and 'whitelist' in node.meta:
            if node.account is not None: # to appease mypy
                whitelist = node.meta['whitelist']
                assert whitelist
                if account.id in whitelist: # if the reader is in the whitelist...
                    pass
                elif len(whitelist) == 1:
                    outgoing_packet['ro'] = 1 # Allow accepting the debate challenge
                else:
                    outgoing_packet['ro'] = 2 # The user may read only
        elif node.parent.data['type'] == 'pod' and node.parent.meta and 'whitelist' in node.parent.meta:
            whitelist = node.parent.meta['whitelist']
            assert whitelist
            assert node.account
            outgoing_packet['ind'] = whitelist.index(node.account.id)

    return outgoing_packet

# Encodes a history entry for the client
def encode_history_entry(entry: Mapping[str, Any], account: session.Account) -> Dict[str, Any]:
    if entry['act'] == 'add':
        return encode_node_for_client(entry['node'], account)
    else:
        assert False, 'Unrecognized history action'

# Returns the mean unbiased ratings and counts for a node
def get_unbiased_ratings(item_id: str) -> Tuple[List[float], int]:
    node = id_to_node(item_id)
    if node.rating_count > 0:
        assert node.ratings
        mean = [ x / node.rating_count for x in node.ratings ]
    else:
        mean = [ 0. for _ in range(len(rec.rating_choices)) ]
    return mean, node.rating_count

# Attaches rating statistics to the updates
def annotate_updates(updates: List[Dict[str, Any]], account: session.Account) -> None:
    item_ids = [ up['id'] for up in updates if (up['act'] == 'add' or up['act'] == 'rate') ]
    if len(item_ids) == 0:
        return
    unbiased_ratings: List[List[float]] = []
    ratings_counts: List[int] = []
    for item_id in item_ids:
        ur, count = get_unbiased_ratings(item_id)
        unbiased_ratings.append(ur)
        ratings_counts.append(count)
    biased_ratings = account.get_biased_ratings(item_ids)
    new_item_threshold = 3 # Number of ratings before an item is no longer considered "new"
    for up, c, ur, br in zip(updates, ratings_counts, unbiased_ratings, biased_ratings):
        # Compute unbiased index, biased index, unbiased score, and biased score for this update and user
        up['ui'], up['bi'], up['us'], up['bs'] = rec.compute_scores(c, ur, br)

# Recursively adds a whole branch of categories to the updates
def add_cat_updates(updates: List[Dict[str, Any]], node: Node, account: session.Account) -> None:
    for c in node.children:
        if c.data['type'] == 'cat':
            updates.append(encode_node_for_client(c, account))
            add_cat_updates(updates, c, account)

def rewrite_pod_history_recursive(op: Node, node: Node) -> None:
    op.history.append({
        'act': 'add',
        'node': node,
    })
    for c in node.children:
        rewrite_pod_history_recursive(op, c)

# Adds history entries to stomp over a pod and all of its children
def rewrite_pod_history(pod: Node) -> None:
    op = pod.parent
    assert op is not None and op.data['type'] == 'op', 'parent of pod should be op'
    rewrite_pod_history_recursive(op, pod)

# Produces a response containing updates the client needs for its tree
def add_updates(updates: List[Dict[str, Any]], ob: Mapping[str, Any], account: session.Account) -> Tuple[int, List[str], List[int]]:
    path = ob['path']
    rev = ob['rev']
    op_list = ob['ops']
    op_revs = ob['opr']
    assert len(op_revs) == len(op_list)

    # Find the ancestor category
    category = id_to_node(path)
    while category.data['type'] != 'cat':
        if len(op_list) == 0 and category.data['type'] == 'op':
            op_list.append(category.id)
            op_revs.append(0)
        assert category.parent
        category = category.parent

    # Do base updates (the stack from the root to the path node)
    if rev < 1:
        stack = category.stack()
        for node in stack:
            updates.append(encode_node_for_client(node, account))
        for id in op_list:
            node = id_to_node(id)
            updates.append(encode_node_for_client(node, account))
        if category.data['type'] == 'cat' and len(category.children) > 0 and category.children[0].data['type'] == 'cat':
            add_cat_updates(updates, category, account)
        rev = 1

    # Do OP updates
    patience = 100
    if len(category.children) < 1 or category.children[0].data['type'] == 'op':
        # Showing a leaf category (the most common case), so update each OP
        for i, op_id in enumerate(op_list):
            if patience == 0:
                break
            op = id_to_node(op_id)
            while op_revs[i] < len(op.history):
                updates.append(encode_history_entry(op.history[op_revs[i]], account))
                op_revs[i] += 1
                patience -= 1
                if patience == 0:
                    break

    return rev, op_list, op_revs

tag_whitelist = set([
    'a',
    '/a',
    'b',
    '/b',
    'i',
    '/i',
    'u',
    '/u',
    'img',
    'table',
    '/table',
    'tr',
    '/tr',
    'td',
    '/td',
    'menu',
    '/menu',
    'hr',
    'ul',
    '/ul',
    'ol',
    '/ol',
    'li',
    '/li',
    'sub',
    '/sub',
    'sup',
    '/sup',
])

def restore_whitelisted_tags(text: str) -> str:
    pos = 0
    while True:
        print(f'pos={pos}')
        open_start = text.find('&lt;', pos)
        print(f'open_start={open_start}')
        pos = open_start + 1
        if open_start < 0:
            print('no more tags')
            break
        close_start = text.find('&gt;', open_start + 4)
        if close_start >= 0:
            first_space = text.find(' ', open_start + 4)
            if first_space == -1:
                first_space = len(text)
            first_slash = text.find('/', open_start + 5)
            if first_slash == -1:
                first_slash = len(text)
            tag_name = text[open_start+4:min(close_start,first_space,first_slash)]
            print(f'tag_name={tag_name}')
            if tag_name in tag_whitelist:
                print('bef: ' + text)
                text = text[:open_start] + '<' + text[open_start+4:close_start] + '>' + text[close_start+4:]
                print('aft: ' + text)
                pos = max(pos, open_start + 1 + (close_start - open_start - 4) + 1)
            else:
                print(f'{tag_name} not in whitelist')
        else:
            print('no close')
    return text

# Formats a comment for display
def format_comment(text: str, maxlen: int) -> str:
    # Enforce length limit
    if len(text) > maxlen:
        text = text[:maxlen]
    text = text.replace('&', '&amp;');
    text = text.replace('>', '&gt;');
    text = text.replace('<', '&lt;');
    text = text.replace('\n', '<br>')
    text = text.replace('  ', '&nbsp; ')
    text = restore_whitelisted_tags(text)
    return text

def summarize_post(id: str, n: int) -> str:
    node = id_to_node(id)
    text = str(node.data['text'])
    summary = text[:n] + ('...' if len(text) > n else '')
    return summary

# Handles POST requests
def do_ajax(incoming_packet: Mapping[str, Any], session_id: str) -> Dict[str, Any]:
    updates: List[Dict[str, Any]] = []
    try:
        if not 'act' in incoming_packet or not 'rev' in incoming_packet or not 'ops' in incoming_packet:
            raise ValueError('malformed request')
        account = session.get_session(session_id).active_account
        act = incoming_packet['act']
        if act == 'update': # Just get updates
            pass
        elif act == 'rate': # Rate a comment
            node = id_to_node(incoming_packet['id'])
            node.rate(incoming_packet['ratings']) # unbiased
            account.rate(incoming_packet['id'], incoming_packet['ratings']) # biased
            updates.append({
                'act': 'rate',
                'id': incoming_packet['id'],
                'cc': account.comment_count,
                'rc': account.ratings_count,
            })
            text = node.data['text']
            if node.account is not None and node.account != account:
                node.account.notif_in.append(('rate', node.id, ''))
        elif act == 'comment': # Post a response comment
            if not 'text' in incoming_packet:
                raise ValueError('expected a text field')
            # if account.comment_count * 2 >= account.ratings_count:
            #     updates.append({
            #         'act': 'alert',
            #         'msg': 'Sorry, you have rated {account.ratings_count} comments and have posted {account.comment_count}.\nA 2:1 ratio is required, so you must rate more comments before you may post.',
            #     })
            # else:
            text = format_comment(incoming_packet['text'], 1000)
            par = id_to_node(incoming_packet['parid'])
            child = Node(par, {'type':'rp', 'text':text}, None, account)
            account.comment_count += 1
            updates.append({
                'act': 'focus',
                'id': child.id,
                'cc': account.comment_count,
                'rc': account.ratings_count,
            })
            summary = text[:50] + '...' if len(text) > 50 else ''
            print(f'Added node {child.id} with text \'{summary}\'')
            while par.data['type'] == 'rp':
                if par.account is not None and par.account != account:
                    par.account.notif_in.append(('rp', par.id, account.id))
            if par.data['type'] == 'pod':
                assert par.parent is not None
                par = par.parent
                if par.data['type'] == 'op':
                    assert par.account is not None and par.account != account
                    par.account.notif_in.append(('op', par.id, account.id))
        elif act == 'newop': # Start a new debate
            if not 'text' in incoming_packet:
                raise ValueError('expected a text field')
            text = format_comment(incoming_packet['text'], 1500)
            cat = id_to_node(incoming_packet['parid'])
            assert cat.data['type'] == 'cat', 'Not a category'
            assert len(cat.children) == 0 or cat.children[0].data['type'] == 'op', 'Please choose a sub-category for your debate'
            op = Node(cat, {'type':'op', 'text':text}, None, account)
            if incoming_packet['mode'] == 'open':
                Node(op, {'type':'pod', 'text':'Open discussion'}, None, account)
            else:
                whitelist: List[str] = [account.id]
                if incoming_packet['mode'] == 'name':
                    opponent = incoming_packet['name']
                    opponent_account = session.find_account_by_name(opponent)
                    whitelist.append(opponent_account.id)
                    opponent_account.notif_in.append(('chal', op.id, account.id))
                Node(op, {'type':'pod', 'text':'One-on-one debate'}, {'whitelist':whitelist}, account)
                Node(op, {'type':'pod', 'text':'Peanut gallery'}, None, account)
            summary = text[:50] + '...' if len(text) > 50 else ''
            updates.append({
                'act': 'pushop',
                'id': op.id,
            })
            print(f'Added op {op.id} with text \'{summary}\'')
        elif act == 'accept': # Accept a debate challenge
            print(f'{account.name} accepted a debate challenge')
            pod_id = incoming_packet['id']
            pod = id_to_node(pod_id)
            assert pod.data['type'] == 'pod', 'not a pod'
            if pod.meta is not None and 'whitelist' in pod.meta and len(pod.meta['whitelist']) < 2 and not account.id in pod.meta['whitelist']:
                pod.meta['whitelist'].append(account.id)
                rewrite_pod_history(pod)
                assert pod.parent is not None
                op = pod.parent
                opponent_account = session.find_account_by_id(pod.meta['whitelist'][0])
                opponent_account.notif_in.append(('acc', op.id, account.id))
            else:
                updates.append({
                    'act': 'alert',
                    'msg': 'Sorry, someone else accepted this challenge first',
                })
        elif act == 'notifs': # Get notifications
            account.digest_notifications()
            updates.append({
                'act': 'notifs',
                'pos': account.notif_pos,
                'msgs': [
                    {
                        'type': m[0],
                        'id': m[1],
                        'image': m[2],
                        'name': m[3],
                        'summ': summarize_post(m[1], 30),
                    }
                    for m in account.notif_out ]
            })
        else:
            raise RuntimeError('unrecognized action')
    except Exception as e:
        updates.append({
            'act': 'alert',
            'msg': str(e),
        })
    new_rev, new_op_list, new_op_revs = add_updates(updates, incoming_packet, account)
    annotate_updates(updates, account)
    updates.append({
        'act': 'nc', # notification count
        'val': len(account.notif_in),
    })
    return {
        'rev': new_rev,
        'ops': new_op_list,
        'opr': new_op_revs,
        'updates': updates,
    }

def pick_ops(path: str) -> List[str]:
    op_list: List[str] = []
    n = id_to_node(path)
    if len(n.children) > 0 and n.children[0].data['type'] == 'op':
        for i in reversed(range(len(n.children))):
            op_list.append(f'{path}.{i}')
            if len(op_list) >= 6:
                break
    return op_list

def do_feed(query: Mapping[str, Any], session_id: str) -> str:
    account = session.get_session(session_id).active_account
    path = query['path'] if 'path' in query else ''
    op_list = pick_ops(path)
    globals = [
        'let session_id = \'', session_id, '\';\n',
        'let path = "', path, '";\n',
        'let op_list = ', str(op_list), ';\n',
        'let comment_count = ', str(account.comment_count), ';\n',
        'let rating_count = ', str(account.ratings_count), ';\n',
        'let rating_choices = ', str([ x[1] for x in rec.rating_choices ]), ';\n',
        'let rating_descr = ', str([ x[2] for x in rec.rating_choices ]), ';\n',
    ]
    updated_feed_page = feed_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_feed_page
