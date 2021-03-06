from typing import List, Mapping, Dict, Any, cast, Tuple, Optional
import sessions
import webserver
from PIL import Image
import random
import string
import rec
from indexable_dict import IndexableDict
import os
from db import db
import cache
import traceback
import posts

auto_name_1 = [
 'amazing', 'awesome', 'blue', 'brave', 'calm', 'cheesy', 'confused', 'cool', 'crazy', 'crafty',
 'delicate', 'diligent', 'dippy', 'exciting', 'fearless', 'flaming', 'fluffy', 'friendly', 'funny', 'gentle',
 'glowing', 'golden', 'greasy', 'green', 'gritty', 'happy', 'jumpy', 'killer', 'laughing', 'liquid',
 'lovely', 'lucky', 'malted', 'meaty', 'mellow', 'melted', 'moldy', 'peaceful', 'pickled', 'pious',
 'purple', 'quiet', 'red', 'rubber', 'sappy', 'silent', 'silky', 'silver', 'sneaky', 'stellar',
 'subtle', 'super', 'special', 'trippy', 'uber', 'valiant', 'vicious', 'wild', 'yellow', 'zippy',
]

auto_name_2 = [
 'alligator','ant', 'armadillo','bat', 'bear', 'bee', 'beaver', 'camel', 'cat', 'cheetah',
 'chicken', 'cricket', 'deer', 'dinosaur', 'dog', 'dolphin', 'duck', 'eagle', 'elephant', 'fish',
 'frog', 'giraffe', 'hamster', 'hawk', 'hornet', 'horse', 'iguana', 'jaguar', 'kangaroo', 'lion',
 'lemur', 'leopard', 'llama', 'monkey', 'mouse', 'newt', 'ninja', 'ox', 'panda', 'panther',
 'parrot', 'porcupine','possum', 'raptor', 'rat', 'salmon', 'shark', 'snake', 'spider', 'squid',
 'tiger', 'toad', 'toucan', 'turtle', 'unicorn', 'walrus', 'warrior', 'wasp', 'wizard', 'yak',
 'zebra'
]

auto_name_3 = [
 'arms', 'beak', 'beard', 'belly', 'belt', 'brain', 'bray', 'breath', 'brow', 'burrito',
 'button', 'cheeks', 'chin', 'claw', 'crown', 'dancer', 'dream', 'dish', 'eater', 'elbow',
 'eye', 'feather', 'finger', 'fist', 'foot', 'forehead', 'fur', 'grin', 'hair', 'hands',
 'head', 'horn', 'jaw', 'knee', 'knuckle', 'legs', 'mouth', 'neck', 'nose', 'pants',
 'party', 'paw', 'pelt', 'pizza', 'platter', 'roar', 'scalp', 'shoe', 'shoulder', 'skin',
 'smile', 'taco', 'tail', 'tamer', 'toe', 'tongue', 'tooth', 'wart', 'wing', 'zit',
]

def new_account_id() -> str:
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(12))

class Account():
    def __init__(self, id: str, name: str, image: str) -> None:
        self.id = id
        self.session_id = ''
        self.name = name
        self.password = ''
        self.image = image
        self.admin = True if (len(account_cache) == 0 and db.have_no_accounts()) else False
        self.comments: List[str] = []
        self.rating_count = 0
        self.ai_on = False
        self.thresh = 25
        self.banned = False

    def marshal(self) -> Mapping[str, Any]:
        packet = {
            'sess': self.session_id,
            'name': self.name,
            'pw': self.password,
            'image': self.image,
            'comments': self.comments,
            'rats': self.rating_count,
            'admin': self.admin,
            'ai_on': self.ai_on,
            'thresh': self.thresh,
            'banned': self.banned,
        }
        return packet

    @staticmethod
    def unmarshal(id: str, ob: Mapping[str, Any]) -> 'Account':
        account = Account(id, ob['name'], ob['image'])
        account.session_id = ob['sess']
        account.password = ob['pw']
        account.comments = ob['comments']
        account.rating_count = ob['rats']
        account.admin = ob['admin']
        account.ai_on = ob['ai_on']
        account.thresh = ob['thresh']
        account.banned = ob['banned']
        return account

def fetch_account(id: str) -> Account:
    return Account.unmarshal(id, db.get_account(id))

def store_account(id: str, _account: Account) -> None:
    assert id == _account.id, 'mismatching ids'
    db.put_account(id, _account.marshal())

account_cache: cache.Cache[str,Account] = cache.Cache(300, fetch_account, store_account)

def find_account_by_name(name: str) -> Account:
    account_cache.flush()
    packet = db.get_account_by_name(name)
    if packet['_id'] in account_cache:
        return account_cache[packet['_id']]
    else:
        acc = Account.unmarshal(packet['_id'], packet)
        return account_cache.add(acc.id, acc)

def make_starter_account() -> Account:
    n1 = random.randrange(len(auto_name_1))
    n2 = random.randrange(len(auto_name_2))
    n3 = random.randrange(len(auto_name_3))
    name = f'{auto_name_1[n1]} {auto_name_2[n2]} {auto_name_3[n3]}'
    image = f'starter_pics/{auto_name_2[n2]}.jpeg'
    account = Account(new_account_id(), name, image)
    return account_cache.add(account.id, account)

def scrub_name(s: str) -> str:
    s = s[:100]
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s


# Load the account page
with open('accounts.html') as f:
    lines = f.readlines()
    account_page = ''.join(lines)

def do_ajax(ob: Mapping[str, Any], session: sessions.Session) -> Dict[str, Any]:
    try:
        act = ob['act']
        if act == 'update':
            account = active_account(session)
            pos = ob['comments_pos']
            comments: List[Tuple[str, str]] = []
            for i in range(30):
                if pos == 0:
                    break
                pos -= 1
                post_id = account.comments[pos]
                comments.append((post_id, posts.summarize_post(post_id, 50)))
            return { 'comments_pos': pos, 'comments': comments }
        elif act == 'logout':
            session.switch_account('', '')
            return { 'reload': True }
        elif act == 'switch':
            try:
                session.switch_account(ob['name'], ob['pw'])
            except KeyError:
                raise ValueError('Unrecognized user name')
            return { 'reload': True }
        elif act == 'change_name':
            newname = scrub_name(ob['name'])
            existing_account: Optional[Account] = None
            try:
                existing_account = find_account_by_name(newname) # flushes accounts, so the account must be retrieved after this line
            except KeyError:
                pass
            if existing_account is None:
                account = active_account(session)
                account.name = newname
                account_cache.set_modified(account.id)
                reloaded = account_cache[account.id]
                reloaded_again = account_cache[account.id]
            else:
                return { 'alert': 'Sorry, that name is already taken.' }
        elif act == 'change_pw':
            account = active_account(session)
            account.password = ob['pw']
            account_cache.set_modified(account.id)
            return { 'have_pw': len(account.password) > 0 }
        elif act == 'drop_account':
            index = ob['index']
            if session.active_index >= index:
                session.active_index = max(0, session.active_index - 1)
            del session.account_ids[index]
            sessions.session_cache.set_modified(session.id)
        elif act == 'ban':
            account = active_account(session)
            if not account.admin:
                raise ValueError('Only an admin can perform that operation')
            session_id = ob['id']
            sess = sessions.session_cache[session_id]
            sess.banned = True
            sessions.session_cache.set_modified(session_id)
            for acc_id in sess.account_ids:
                acc = account_cache[acc_id]
                acc.banned = True
                account_cache.set_modified(acc_id)
            rec.engine.banned_addresses.add(sess.addr)
        else:
            raise RuntimeError('unrecognized action')
        return {}
    except Exception as e:
        traceback.print_exc()
        return {
            'alert': str(e), # repr(e),
        }

def do_account(query: Mapping[str, Any], session: sessions.Session) -> str:
    account = active_account(session)
    if 'id' in query:
        account_to_show = account_cache[query['id']]
    else:
        account_to_show = account
    if account_to_show is account:
        accounts = [ account_cache[id] for id in session.account_ids ]
    else:
        accounts = []
    globals = [
        'let session_id = \'', session.id, '\';\n',
        'let admin = ', 'true' if account.admin else 'false', ';\n',
        'let isself = ', 'true' if account is account_to_show else 'false', ';\n',
        'let username = \'', account_to_show.name, '\';\n',
        'let profile_pic = \'', account_to_show.image, '\';\n',
        'let have_pw = ', 'true' if len(account.password) > 0 or not account_to_show is account else 'false', ';\n',
        'let account_names = ', str([a.name for a in accounts]), ';\n',
        'let account_images = ', str([a.image for a in accounts]), ';\n',
        'let prev_query = ', str(session.query), ';\n',
        'let comments_pos = ', str(len(account.comments)), ';\n',
    ]
    updated_account_page = account_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_account_page

def do_error_page(err: str, session: sessions.Session) -> str:
    return f'<html><body>{err}</body></html>'

def receive_image(query: Mapping[str, Any], session: sessions.Session) -> str:
    account = active_account(session)

    # Receive the file
    temp_filename = f'/tmp/{account.id}.jpeg'
    try:
        webserver.sws.receive_file(temp_filename, 4000000)
    except Exception as e:
        return do_error_page(str(e), session)

    # Scale and crop the image
    img = Image.open(temp_filename)
    img = img.resize((48 * img.size[0] // img.size[1], 48), Image.ANTIALIAS)
    img = img.convert('RGB')
    if img.size[0] > 64:
    	left = (img.size[0] - 64) / 2
    	img = img.crop((left, 0, left + 64, 48))
    final_filename = f'profile_pics/{account.id}.jpeg'
    img.save(final_filename)

    # Update the profile pic
    account.image = final_filename
    return do_account(query, session)

def active_account(session: sessions.Session) -> Account:
    account = account_cache[session.account_ids[session.active_index]]
    if account.banned:
        rec.engine.banned_addresses.add(session.addr)
        raise ValueError('Banned account')
    return account
