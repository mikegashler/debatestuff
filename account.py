from typing import List, Mapping, Dict, Any, cast, Tuple, Optional
import session
import webserver
from PIL import Image
import random
import string
import rec
from indexable_dict import IndexableDict
import os

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

id_to_account: Dict[str, "Account"] = {}

class Account():
    def __init__(self, name: str, image: str, id: str) -> None:
        self.id = id
        self.name = name
        self.password = ''
        self.image = image
        self.admin = False
        self.comment_count = 0
        self.ratings: IndexableDict[str, List[float]] = IndexableDict()
        self.notif_in: List[Tuple[str, str, str]] = [] # type, post id, account id
        self.notif_out: List[Tuple[str, str, str, str]] = [] # type, post id, image, name
        self.notif_pos = 0
        id_to_account[id] = self

    def marshal(self) -> Mapping[str, Any]:
        packet = {
            'id': self.id,
            'name': self.name,
            'pw': self.password,
            'image': self.image,
            'coms': self.comment_count,
            'hist': self.ratings.marshal(),
            'notif_in': self.notif_in,
            'notif_out': self.notif_out,
            'notif_pos': self.notif_pos,
        }
        if self.admin:
            packet['admin'] = True
        return packet

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Account':
        account = Account(ob['name'], ob['image'], ob['id'])
        account.password = ob['pw']
        account.comment_count = ob['coms']
        account.ratings = IndexableDict.unmarshal(ob['hist'])
        account.notif_in = ob['notif_in']
        account.notif_out = ob['notif_out']
        account.notif_pos = ob['notif_pos']
        if 'admin' in ob:
            account.admin = ob['admin']
        return account

    def rate(self, item_id: str, ratings: List[float]) -> None:
        self.ratings[item_id] = ratings
        rec.engine.prepare_rating_profiles(self.id, item_id)
        rec.engine.train()

    # Returns ratings for the specified list of item_ids.
    # If this account has previously rated the item, returns those ratings instead.
    # If there is no profile for the item (because no one has ever rated it), returns [].
    def get_biased_ratings(self, item_ids: List[str]) -> List[List[float]]:
        if not self.id in rec.engine.user_profiles:
            return [ [] for _ in item_ids ] # This account has never rated anything
        rated = [ (item_id in self.ratings) for item_id in item_ids ] # List of bools. True iff this account has rated the item
        unrated = [ item_ids[i] for i in range(len(rated)) if not rated[i] ] # List of item ids that need rating
        can_be_rated = [ (item_id in rec.engine.item_profiles) for item_id in unrated ] # List of bools. True iff the item can be rated
        rate_me = [ unrated[i] for i in range(len(can_be_rated)) if can_be_rated[i] ] # List of item ids to rate
        self_ids = [ self.id for _ in rate_me ]
        ratings = rec.engine.predict(self_ids, rate_me)
        j = 0
        k = 0
        results: List[List[float]] = []
        for i in range(len(item_ids)):
            if rated[i]:
                results.append(self.ratings[item_ids[i]])
            else:
                if can_be_rated[j]:
                    results.append(ratings[k])
                    k += 1
                else:
                    results.append([])
                j += 1
        assert j == len(unrated) and k == len(rate_me), 'something is broken'
        return results

    # Extract a group of notifications that all have the same type and node id
    def group_notifs(self) -> List[Tuple[str, str, str]]:
        group: List[Tuple[str, str, str]] = []
        tail = self.notif_in[len(self.notif_in) - 1]
        group.append(tail)
        del self.notif_in[len(self.notif_in) - 1]
        for i in reversed(range(len(self.notif_in))):
            notif = self.notif_in[i]
            if notif[0] == tail[0] and notif[1] == tail[1]:
                group.append(notif)
                del self.notif_in[i]
        return group

    # Consumes self.notif_in. Pushes messages into self.notif_out.
    def digest_notifications(self) -> None:
        self.notif_pos = len(self.notif_out)
        while len(self.notif_in) > 0:
            while len(self.notif_out) >= 30:
                del self.notif_out[0]
                self.notif_pos = max(0, self.notif_pos - 1)
            group = self.group_notifs()
            first = group[0]
            if len(first[2]) > 0:
                person = find_account_by_id(first[2])
                name = person.name
                if len(group) == 2:
                    person2 = find_account_by_id(group[1][2])
                    name += f' and {person2.name}'
                elif len(group) > 2:
                    name += f' and {len(group) - 1} others'
                self.notif_out.append((first[0], first[1], person.image, name))
            else:
                name = f'{len(group)} {"person" if len(group) == 1 else "people"}'
                self.notif_out.append((first[0], first[1], 'starter_pics/rate.jpeg', name))

    def notify(self, type: str, node_id: str, account_id: str) -> None:
        assert len(self.notif_in) < 1000, 'Notifications are out of control!'
        self.notif_in.append((type, node_id, account_id))

def find_account_by_id(id: str) -> Account:
    return id_to_account[id]

def find_account_by_name(name: str) -> Account:
    for id in id_to_account:
        if id_to_account[id].name == name:
            return id_to_account[id]
    raise ValueError('No account with that name')

def make_starter_account() -> Account:
    n1 = random.randrange(len(auto_name_1))
    n2 = random.randrange(len(auto_name_2))
    n3 = random.randrange(len(auto_name_3))
    name = f'{auto_name_1[n1]} {auto_name_2[n2]} {auto_name_3[n3]}'
    image = f'starter_pics/{auto_name_2[n2]}.jpeg'
    return Account(name, image, new_account_id())

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
    sess = session.get_session(session_id)
    account = sess.active_account
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
    sess = session.get_session(session_id)
    account = sess.active_account
    globals = [
        'let session_id = \'', session_id, '\';\n',
        'let username = \'', account.name, '\';\n',
        'let profile_pic = \'', account.image, '\';\n',
        'let have_pw = ', 'true' if len(account.password) > 0 else 'false', ';\n',
        'let account_names = ', str([a.name for a in sess.accounts]), ';\n',
        'let account_images = ', str([a.image for a in sess.accounts]), ';\n',
    ]
    updated_account_page = account_page.replace('//<globals>//', ''.join(globals), 1)
    return updated_account_page

def do_error_page(err: str, session_id: str) -> str:
    return f'<html><body>{err}</body></html>'

def receive_image(query: Mapping[str, Any], session_id: str) -> str:
    account = session.get_session(session_id).active_account

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
