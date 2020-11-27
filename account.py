from typing import List, Mapping, Dict, Any, cast, Tuple, Optional
import session
import webserver
from PIL import Image
import random
import string
import rec
from indexable_dict import IndexableDict
import os
from db import db

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
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(16))

account_cache: Dict[str, "Account"] = {}

class Account():
    def __init__(self, id: str, name: str, image: str) -> None:
        self.id = id
        self.name = name
        self.password = ''
        self.image = image
        self.admin = False
        self.comment_count = 0
        # self.notif_pos = 0
        global account_cache
        if len(account_cache) > 500:
            account_cache = {} # Periodically flush the cache so it doesn't get bloated
        account_cache[id] = self

    def marshal(self) -> Mapping[str, Any]:
        packet = {
            '_id': self.id,
            'name': self.name,
            'pw': self.password,
            'image': self.image,
            'coms': self.comment_count,
            'admin': self.admin,
            # 'notif_pos': self.notif_pos,
        }
        return packet

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Account':
        account = Account(ob['_id'], ob['name'], ob['image'])
        account.password = ob['pw']
        account.comment_count = ob['coms']
        account.admin = ob['admin']
        # account.notif_pos = ob['notif_pos']
        return account

    # Extract a group of notifications that all have the same type and node id
    def group_notifs(self, notif_in: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
        group: List[Tuple[str, str, str]] = []
        tail = notif_in[len(notif_in) - 1]
        group.append(tail)
        del notif_in[len(notif_in) - 1]
        for i in reversed(range(len(notif_in))):
            notif = notif_in[i]
            if notif[0] == tail[0] and notif[1] == tail[1]:
                group.append(notif)
                del notif_in[i]
        return group

    # Consumes notif_in. Pushes messages into notif_out and returns notif_out
    def digest_notifications(self) -> List[Tuple[str, str, str, str]]:
        # self.notif_pos = len(self.notif_out)
        try:
            notif_in = db.get_notif_in(self.id)
        except KeyError:
            notif_in = []
        dirty = False
        try:
            notif_out = db.get_notif_out(self.id)
        except KeyError:
            notif_out = []
        while len(notif_in) > 0:
            dirty = True
            while len(notif_out) >= 30:
                del notif_out[0]
                # self.notif_pos = max(0, self.notif_pos - 1)
            group = self.group_notifs(notif_in)
            first = group[0]
            if len(first[2]) > 0:
                person = db.get_account(first[2])
                name = person['name']
                if len(group) == 2:
                    person2 = db.get_account(group[1][2])
                    name += f' and {person2["name"]}'
                elif len(group) > 2:
                    name += f' and {len(group) - 1} others'
                notif_out.append((first[0], first[1], person['image'], name))
            else:
                name = f'{len(group)} {"person" if len(group) == 1 else "people"}'
                notif_out.append((first[0], first[1], 'starter_pics/rate.jpeg', name))
        if dirty:
            db.put_notif_out(self.id, notif_out)
            db.put_notif_in(self.id, notif_in)
        return notif_out

    def notify(self, type: str, node_id: str, account_id: str) -> None:
        try:
            notif_in = db.get_notif_in(self.id)
        except KeyError:
            notif_in = []
        assert len(notif_in) < 1000, 'Notifications are out of control!'
        notif_in.append((type, node_id, account_id))
        db.put_notif_in(self.id, notif_in)

def find_account_by_id(id: str) -> Account:
    if id in account_cache:
        return account_cache[id]
    packet = db.get_account(id)
    return Account.unmarshal(packet)

def find_account_by_name(name: str) -> Account:
    packet = db.get_account_by_name(name)
    if packet['_id'] in account_cache:
        return account_cache[packet['_id']]
    else:
        return Account.unmarshal(packet)

def make_starter_account() -> Account:
    n1 = random.randrange(len(auto_name_1))
    n2 = random.randrange(len(auto_name_2))
    n3 = random.randrange(len(auto_name_3))
    name = f'{auto_name_1[n1]} {auto_name_2[n2]} {auto_name_3[n3]}'
    image = f'starter_pics/{auto_name_2[n2]}.jpeg'
    account = Account(new_account_id(), name, image)
    db.put_account(account.marshal())
    return account

def scrub_name(s: str) -> str:
    s = s[:100]
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    return s


# Load the account page
if not os.path.exists('account.html'):
    os.chdir('/home/mike/bin/debate/')
with open('account.html') as f:
    lines = f.readlines()
    account_page = ''.join(lines)

def do_ajax(ob: Mapping[str, Any], session_id: str) -> Dict[str, Any]:
    sess = session.get_or_make_session(session_id)
    account = sess.active_account()
    act = ob['act']
    if act == 'logout':
        sess.switch_account('')
        return { 'reload': True }
    elif act == 'switch':
        sess.switch_account(ob['name'])
        return { 'reload': True }
    elif act == 'change_name':
        newname = scrub_name(ob['name'])
        account.name = newname
    elif act == 'change_pw':
        account.password = ob['pw']
        return { 'have_pw': len(account.password) > 0 }
    else:
        raise RuntimeError('unrecognized action')
    return {}

def do_account(query: Mapping[str, Any], session_id: str) -> str:
    sess = session.get_or_make_session(session_id)
    account = sess.active_account()
    accounts = [ find_account_by_id(id) for id in sess.account_ids ]
    globals = [
        'let session_id = \'', session_id, '\';\n',
        'let username = \'', account.name, '\';\n',
        'let profile_pic = \'', account.image, '\';\n',
        'let have_pw = ', 'true' if len(account.password) > 0 else 'false', ';\n',
        'let account_names = ', str([a.name for a in accounts]), ';\n',
        'let account_images = ', str([a.image for a in accounts]), ';\n',
    ]
    updated_account_page = account_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_account_page

def do_error_page(err: str, session_id: str) -> str:
    return f'<html><body>{err}</body></html>'

def receive_image(query: Mapping[str, Any], session_id: str) -> str:
    account = session.get_or_make_session(session_id).active_account()

    # Receive the file
    temp_filename = f'/tmp/{account.id}.jpeg'
    try:
        webserver.sws.receive_file(temp_filename, 4000000)
    except Exception as e:
        return do_error_page(str(e), session_id)

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
    return do_account(query, session_id)
