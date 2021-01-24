from typing import List, Mapping, Dict, Any, cast, Tuple, Optional, Set
import webserver
import urllib.parse
import json
import sessions
import random
import rec
import accounts
import traceback
import posts
import history
import notifs
from PIL import Image

# Load the feed page
with open('feed.html') as f:
    lines = f.readlines()
    feed_page = ''.join(lines)

# Finds the index of the strongest rating, and computes an overall score for the item
def compute_score(ratings: List[float]) -> Tuple[int, float]:
    assert len(ratings) == len(rec.rating_choices), 'expected a rating for each choice'
    max_index = 0
    max_val = -1000000.
    score = 0.
    for i in range(len(rec.rating_choices)):
        score += ratings[i] * rec.rating_choices[i][0]
        if ratings[i] > max_val:
            max_val = ratings[i]
            max_index = i
    return max_index, score

# Returns aioff index, aion index, aioff score, and aion score for a particular node and user.
def compute_scores(item_ratings_count: int, aioff_ratings: List[float], aion_ratings: List[float]) -> Tuple[int, int, float, float]:
    if item_ratings_count < 1:
        return 0, 0, 1000., 1000. # This item has never been rated
    max_aioff_index, aioff_score = compute_score(aioff_ratings)
    if len(aion_ratings) == 0:
        max_aion_index = 0
        aion_score = 1000.
    else:
        max_aion_index, aion_score = compute_score(aion_ratings)
    return max_aioff_index, max_aion_index, aioff_score, aion_score

# Attaches rating statistics to the updates
def annotate_updates(updates: List[Dict[str, Any]], account: accounts.Account) -> None:
    post_ids = [ up['id'] for up in updates if (up['act'] == 'add' or up['act'] == 'rate') ]
    if len(post_ids) == 0:
        return
    aioff_ratings: List[List[float]] = []
    ratings_counts: List[int] = []
    for post_id in post_ids:
        post = posts.post_cache[post_id]
        ur, count = post.get_aioff_ratings()
        aioff_ratings.append(ur)
        ratings_counts.append(count)
    aion_ratings = rec.engine.get_ratings(account.id, post_ids)
    new_item_threshold = 3 # Number of ratings before an item is no longer considered "new"
    for up, c, ur, br in zip(updates, ratings_counts, aioff_ratings, aion_ratings):
        # Compute aioff index, aion index, aioff score, and aion score for this update and user
        up['ui'], up['bi'], up['us'], up['bs'] = compute_scores(c, ur, br)


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
        open_start = text.find('&lt;', pos)
        pos = open_start + 1
        if open_start < 0:
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
            if tag_name in tag_whitelist:
                text = text[:open_start] + '<' + text[open_start+4:close_start] + '>' + text[close_start+4:]
                pos = max(pos, open_start + 1 + (close_start - open_start - 4) + 1)
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

def delete_post(post_id: str) -> None:
    post = posts.post_cache[post_id]
    par = posts.post_cache[post.parent_id]
    index = par.children.index(post_id)
    del par.children[index]
    if len(post.op_id) > 0:
        history.rewrite_op_history(post.op_id)
    # todo: recursively remove the post and all its children from the database

# Recursively adds a whole branch of categories to the updates
def add_cat_updates(updates: List[Dict[str, Any]], post: posts.Post, account_id: str, depth: int) -> None:
    import posts
    for c in post.children:
        child_post = posts.post_cache[c]
        if not child_post.type == 'cat':
            break
        updates.append(child_post.encode_for_client(account_id, depth))
        add_cat_updates(updates, child_post, account_id, depth + 1)

# Adds post updates the client needs for its tree
def add_updates(updates: List[Dict[str, Any]], incoming_packet: Mapping[str, Any], account_id: str) -> Tuple[int, List[str], List[int]]:
    import posts
    focus_post_id = incoming_packet['post']
    rev = incoming_packet['rev']
    op_list = incoming_packet['ops']
    op_revs = incoming_packet['opr']
    assert len(op_revs) == len(op_list)

    # Find the ancestor category (and pick up the op if we don't have any)
    depth = -1 # depth above the OP
    category = posts.post_cache[focus_post_id]
    while category.type != 'cat':
        if len(op_list) == 0 and category.type == 'op':
            op_list.append(category.id)
            op_revs.append(0)
        assert len(category.parent_id) > 0
        category = posts.post_cache[category.parent_id]
        depth += 1

    # Do platform updates
    if rev < 1:
        # Add the stack from the root to the post node
        stack: List[posts.Post] = []
        n = category
        while True:
            stack.append(n)
            if len(n.parent_id) > 0:
                n = posts.post_cache[n.parent_id]
            else:
                break
        stack.reverse()
        for i, node in enumerate(stack):
            updates.append(node.encode_for_client(account_id, i))

        # Add the sub-branch of categories
        if len(category.children) > 0 and posts.post_cache[category.children[0]].type == 'cat':
            add_cat_updates(updates, category, account_id, len(stack))

        # Add the OPs in the op_list
        for id in op_list:
            post = posts.post_cache[id]
            updates.append(post.encode_for_client(account_id, 0))
        rev = 1

    # Do OP updates
    patience = 100
    if len(category.children) == 0 or posts.post_cache[category.children[0]].type == 'op':
        for i, op_id in enumerate(op_list):
            if patience == 0:
                break
            try:
                op_hist = history.history_cache[op_id]
            except KeyError:
                break
            op_revs[i] = max(op_revs[i], op_hist.start)
            while op_revs[i] < op_hist.revs():
                post_id = op_hist.get_rev(op_revs[i])
                post = posts.post_cache[post_id]
                updates.append(post.encode_for_client(account_id, depth))
                op_revs[i] += 1
                patience -= 1
                if patience == 0:
                    break

    return rev, op_list, op_revs

# Handles POST requests
def do_ajax(incoming_packet: Mapping[str, Any], session: sessions.Session) -> Dict[str, Any]:
    updates: List[Dict[str, Any]] = []
    try:
        if not 'act' in incoming_packet:
            raise ValueError('malformed request')
        account = accounts.active_account(session)
        act = incoming_packet['act']
        if act == 'update': # Just get updates
            pass
        elif act == 'react': # React to a post
            post = posts.post_cache[incoming_packet['id']]
            emo = incoming_packet['emo']
            if emo < 0 or emo >= 12:
                raise ValueError('out of range emoticon index')
            post.emos.append((emo, account.name))
            notifs.notify(post.account_id, f'react_{emo}', post.id, account.id)
            updates.append({
                'act': 'emo',
                'id': incoming_packet['id'],
                'emo': emo,
                'name': account.name,
            })
        elif act == 'rate': # Rate a comment
            post = posts.post_cache[incoming_packet['id']]
            if post.account_id == account.id:
                updates.append({
                    'act': 'alert',
                    'msg': 'Sorry, rating your own posts is not allowed',
                })
            else:
                rec.engine.rate(account.id, incoming_packet['id'], incoming_packet['ratings'])
                updates.append({
                    'act': 'rate',
                    'id': incoming_packet['id'],
                })
                notifs.notify(post.account_id, 'rate', post.id, '')
        elif act == 'comment': # Post a response comment
            if not 'text' in incoming_packet:
                raise ValueError('expected a text field')
            # if len(account.comments) * 2 >= account.ratings_count:
            #     updates.append({
            #         'act': 'alert',
            #         'msg': 'Sorry, you have rated {account.ratings_count} comments and have posted {len(account.comments)}.\nA 2:1 ratio is required, so you must rate more comments before you may post.',
            #     })
            # else:
            text = format_comment(incoming_packet['text'], 1000)
            par = posts.post_cache[incoming_packet['parid']]
            new_post_id = posts.new_post_id()
            child = posts.new_post(new_post_id, incoming_packet['parid'], 'rp', text, account.id)
            account.comments.append(child.id)
            accounts.account_cache.set_modified(account.id)
            updates.append({
                'act': 'focus',
                'id': child.id,
            })
            summary = text[:50] + '...' if len(text) > 50 else ''
            print(f'Added post {child.id} with text \'{summary}\'')

            # Notify the owners of all ancestor posts about this comment
            ancestor = par
            visited: Set[str] = set()
            while ancestor.type == 'rp':
                if ancestor.account_id != account.id and not ancestor.account_id in visited:
                    visited.add(ancestor.account_id)
                    notifs.notify(ancestor.account_id, 'rp', ancestor.id, account.id)
                if len(ancestor.parent_id) == 0:
                    break
                else:
                    ancestor = posts.post_cache[ancestor.parent_id]
            if ancestor.type == 'pod':
                assert len(ancestor.parent_id) > 0, 'expected a valid parent id'
                ancestor = posts.post_cache[ancestor.parent_id]
                if ancestor.type == 'op':
                    assert len(ancestor.account_id) > 0, 'expected a valid account id'
                    if ancestor.account_id != account.id and not ancestor.id in visited:
                        notifs.notify(ancestor.account_id, 'op', ancestor.id, account.id)
        elif act == 'newop': # Start a new debate
            if not 'text' in incoming_packet:
                raise ValueError('expected a text field')
            text = format_comment(incoming_packet['text'], 1500)
            cat = posts.post_cache[incoming_packet['parid']]
            assert cat.type == 'cat', 'Not a category'
            assert len(cat.children) == 0 or posts.post_cache[cat.children[0]].type == 'op', 'Please choose a sub-category for your debate'
            new_op_id = posts.new_post_id()
            op = posts.new_post(new_op_id, cat.id, 'op', text, account.id)
            if incoming_packet['mode'] == 'open':
                new_pod_id = posts.new_post_id()
                posts.new_post(new_pod_id, new_op_id, 'pod', 'Open discussion', account.id)
            else:
                whitelist: List[str] = [account.id]
                if incoming_packet['mode'] == 'name':
                    opponent_name = incoming_packet['name']
                    opponent_account = accounts.find_account_by_name(opponent_name)
                    whitelist.append(opponent_account.id)
                    notifs.notify(opponent_account.id, 'chal', op.id, account.id)
                new_pod_id = posts.new_post_id()
                new_pod = posts.new_post(new_pod_id, new_op_id, 'pod', 'One-on-one debate', account.id)
                new_pod.wl = whitelist
                new_pod_id = posts.new_post_id()
                posts.new_post(new_pod_id, new_op_id, 'pod', 'Peanut gallery', account.id)
            summary = text[:50] + '...' if len(text) > 50 else ''
            updates.append({
                'act': 'pushop',
                'id': op.id,
            })
            print(f'Added op {op.id} with text \'{summary}\'')
        elif act == 'accept': # Accept a debate challenge
            print(f'{account.name} accepted a debate challenge')
            pod_id = incoming_packet['id']
            pod = posts.post_cache[pod_id]
            assert pod.type == 'pod', 'not a pod'
            if len(pod.wl) == 1 and not account.id in pod.wl:
                pod.wl.append(account.id)
                history.rewrite_op_history(pod.op_id)
                history.history_cache.set_modified(pod.op_id)
                assert len(pod.parent_id) > 0, 'invalid parent id'
                opponent_account = accounts.account_cache[pod.wl[0]]
                notifs.notify(opponent_account.id, 'acc', pod.op_id, account.id)
            else:
                updates.append({
                    'act': 'alert',
                    'msg': 'Sorry, someone else accepted this challenge first',
                })
        elif act == 'notifs': # Get notifications
            digested_notifications = notifs.digest_notifications(account.id)
            notifs_out = notifs.notif_out_cache[account.id]
            updates.append({
                'act': 'notifs',
                'pos': notifs_out.pos,
                'msgs': [
                    {
                        'type': m[0],
                        'id': m[1],
                        'image': m[2],
                        'name': m[3],
                        'summ': posts.summarize_post(m[1], 30),
                    }
                    for m in digested_notifications ]
            })
        elif act == 'del': # Delete a post
            ok = True if account.admin else False
            msg = 'Sorry, you lack permission to delete that post'
            if not ok:
                post = posts.post_cache[pod_id]
                if len(post.children) == 0:
                    if post.account_id == account.id:
                        ok = True
                else:
                    msg = 'Sorry, you cannot delete a post someone has already replied to'
            if ok:
                delete_post(incoming_packet['id'])
            else:
                updates.append({
                    'act': 'alert',
                    'msg': msg,
                })
        elif act == 'change_aion': # Turn the AI on or off
            account.ai_on = incoming_packet['on']
            accounts.account_cache.set_modified(account.id)
        elif act == 'change_thresh': # Change the threshold by moving the slider
            account.thresh = incoming_packet['val']
            accounts.account_cache.set_modified(account.id)
        elif act == 'upload': # Receive an uploaded file
            fn = incoming_packet['file']
            max_wid = 600
            max_hgt = 800
            img = Image.open(f'/tmp/{fn}')
            if img.size[0] > max_wid or img.size[1] > max_hgt:
                if img.size[0] / max_wid > img.size[1] / max_hgt:
                    img = img.resize((max_wid, img.size[1] * max_wid // img.size[0]), Image.ANTIALIAS)
                else:
                    img = img.resize((img.size[0] * max_hgt // img.size[1], max_hgt), Image.ANTIALIAS)
            img = img.convert('RGB')
            final_filename = f'post_pics/{fn}'
            img.save(final_filename)
            updates.append({
                'act': 'upload',
                'file': f'post_pics/{fn}'
            })
        else:
            raise RuntimeError('unrecognized action')
    except Exception as e:
        traceback.print_exc()
        updates.append({
            'act': 'alert',
            'msg': str(e), # repr(e),
        })
    if 'rev' in incoming_packet:
        new_rev, new_op_list, new_op_revs = add_updates(updates, incoming_packet, account.id)
        annotate_updates(updates, account)
        notif_in = notifs.get_or_make_notif_in(account.id)
        updates.append({
            'act': 'nc', # notification count
            'val': len(notif_in.notifs),
        })
        return {
            'rev': new_rev,
            'ops': new_op_list,
            'opr': new_op_revs,
            'updates': updates,
        }
    else:
        return {
            'updates': updates,
        }

def pick_ops(post: str) -> Tuple[bool, List[str]]:
    op_list: List[str] = []
    node = posts.post_cache[post]
    is_leaf_cat = (node.type == 'cat' and (len(node.children) == 0 or posts.post_cache[node.children[0]].type == 'op'))
    if is_leaf_cat and len(node.children) > 0:
        for i in reversed(range(len(node.children))):
            op_list.append(node.children[i])
            if len(op_list) >= 6:
                break
    return is_leaf_cat, op_list

def do_feed(query: Mapping[str, Any], session: sessions.Session) -> str:
    session.query = query
    account = accounts.active_account(session)
    post = query['post'] if 'post' in query else '000000000000'
    is_leaf_cat, op_list = pick_ops(post)
    globals = [
        'let session_id = \'', session.id, '\';\n',
        'let post = "', post, '";\n',
        'let op_list = ', str(op_list), ';\n',
        'let allow_new_debate = ', 'true' if is_leaf_cat else 'false', ';\n',
        'let admin = ', 'true' if account.admin else 'false', ';\n',
        'let account_name = \'', account.name, '\';\n',
        'let account_pic = \'', account.image, '\';\n',
        'let comment_count = ', str(len(account.comments)), ';\n',
        'let rating_count = ', str(account.rating_count), ';\n',
        'let rating_choices = ', str([ x[1] for x in rec.rating_choices ]), ';\n',
        'let rating_descr = ', str([ x[2] for x in rec.rating_choices ]), ';\n',
        'let initial_ai_on = ', 'true' if account.ai_on else 'false', ';\n',
        'let initial_thresh = ', str(account.thresh), ';\n',
    ]
    updated_feed_page = feed_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_feed_page
