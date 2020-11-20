from typing import Mapping, Dict, Any, List, Tuple
import string
import random
import rec

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

class Account():
    def __init__(self, name: str, image: str, id: str) -> None:
        self.id = id
        self.name = name
        self.password = ''
        self.image = image
        self.comment_count = 0
        self.ratings_count = 0
        self.ratings_history: Dict[str, List[float]] = {}
        self.notif_in: List[Tuple[str, str, str]] = [] # type, post id, account id
        self.notif_out: List[Tuple[str, str, str, str]] = [] # type, post id, image, name
        self.notif_pos = 0

    def marshal(self) -> Mapping[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'pw': self.password,
            'image': self.image,
            'coms': self.comment_count,
            'rats': self.ratings_count,
            'hist': self.ratings_history,
            'ni': self.notif_in,
            'no': self.notif_out,
            'np': self.notif_pos,
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Account':
        account = Account(ob['name'], ob['image'], ob['id'])
        account.password = ob['pw']
        account.comment_count = ob['coms']
        account.ratings_count = ob['rats']
        account.ratings_history = ob['hist']
        account.notif_in = ob['ni']
        account.notif_out = ob['no']
        account.notif_pos = ob['np']
        return account

    def rate(self, item_id: str, ratings: List[float]) -> None:
        self.ratings_count += 1
        rec.engine.rate(self.id, item_id, ratings)
        self.ratings_history[item_id] = ratings

    def get_biased_ratings(self, item_ids: List[str]) -> List[List[float]]:
        rated = [ (item_id in self.ratings_history) for item_id in item_ids ]
        unrated = [ item_ids[i] for i in range(len(rated)) if not rated[i] ]
        self_ids = [ self.id for _ in unrated ]
        ratings = rec.engine.predict(self_ids, unrated)
        j = 0
        results: List[List[float]] = []
        for i in range(len(item_ids)):
            if rated[i]:
                results.append(self.ratings_history[item_ids[i]])
            else:
                results.append(ratings[j])
                j += 1
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

def make_starter_account() -> Account:
    n1 = random.randrange(len(auto_name_1))
    n2 = random.randrange(len(auto_name_2))
    n3 = random.randrange(len(auto_name_3))
    name = f'{auto_name_1[n1]} {auto_name_2[n2]} {auto_name_3[n3]}'
    image = f'starter_pics/{auto_name_2[n2]}.jpeg'
    return Account(name, image, new_account_id())

class Session():
    def __init__(self, accounts: List[Account], active_index: int) -> None:
        self.accounts = accounts
        self.active_account = self.accounts[active_index]

    def marshal(self) -> Mapping[str, Any]:
        return {
            'ac': [ x.marshal() for x in self.accounts ],
            'aa': self.accounts.index(self.active_account),
        }

    # If account_name is the empty string, this will switch to the first account with no password, creating one if necessary
    def switch_account(self, account_name: str) -> None:
        if len(account_name) == 0:
            for i in range(len(self.accounts)):
                if len(self.accounts[i].password) == 0:
                    self.active_account = self.accounts[i]
                    return
            no_password_account = make_starter_account()
            self.accounts.append(no_password_account)
            self.active_account = no_password_account
        else:
            for i in range(len(self.accounts)):
                if self.accounts[i].name == account_name:
                    self.active_account = self.accounts[i]
                    return
            raise ValueError('No account named {account_name}')

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Session':
        return Session([ Account.unmarshal(x) for x in ob['ac'] ], ob['aa'])

sessions: Dict[str, Session] = {}

def get_session(session_id: str) -> Session:
    if session_id in sessions:
        return sessions[session_id]
    session = Session([ make_starter_account() ], 0)
    sessions[session_id] = session
    return session

def find_account_by_name(name: str) -> Account:
    for sid in sessions:
        sess = sessions[sid]
        for account in sess.accounts:
            if account.name == name:
                return account
    raise ValueError('No account with that name')

# todo: memoize with a lookup dict
def find_account_by_id(id: str) -> Account:
    for sid in sessions:
        sess = sessions[sid]
        for account in sess.accounts:
            if account.id == id:
                return account
    raise ValueError('No account with that id')


def switch_accounts_page(query: Mapping[str, Any], session_id: str) -> str:
    return """<html><body>
<h1>This page is under construction</h1>
</body></html>"""

def account_settings_page(query: Mapping[str, Any], session_id: str) -> str:
    return """<html><body>
<h1>This page is under construction</h1>
</body></html>"""
