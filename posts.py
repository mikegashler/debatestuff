from typing import Mapping, Any, List, Optional, Dict, Tuple
from db import db
import rec
import random
import string
import history
import account
import cache

def new_post_id() -> str:
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(12))

class Post():
    def __init__(self, id: str, parent_id: str, op_id: str, type: str, text: str, account_id: str) -> None:
        self.id = id
        self.parent_id = parent_id
        self.op_id = op_id
        self.type = type
        self.text = text
        self.account_id = account_id
        self.children: List[str] = []
        self.wl: List[str] = []
        self.ratings: Optional[List[int]] = None
        self.rating_count = 0

    def marshal(self) -> Mapping[str, Any]:
        return {
            'par': self.parent_id,
            'op': self.op_id,
            'type': self.type,
            'text': self.text,
            'acc': self.account_id,
            'chil': self.children,
            'wl': self.wl,
            'rats': self.ratings,
            'rc': self.rating_count,
        }

    @staticmethod
    def unmarshal(id: str, ob: Mapping[str, Any]) -> 'Post':
        post = Post(id, ob['par'], ob['op'], ob['type'], ob['text'], ob['acc'])
        post.children = ob['chil']
        post.wl = ob['wl']
        post.ratings = ob['rats']
        post.rating_count = ob['rc']
        return post

    def undo_rating(self, ratings: List[float]) -> None:
        assert self.ratings is not None, 'No ratings to undo!'
        for i in range(len(ratings)):
            assert ratings[i] >= 0. and ratings[i] <= 1., 'rating out of range'
            self.ratings[i] -= max(0, min(1, int(ratings[i])))
        self.rating_count -= 1

    def add_rating(self, ratings: List[float]) -> None:
        if self.ratings is None:
            self.ratings = [ 0 for _ in rec.rating_choices ]
        for i in range(len(ratings)):
            assert ratings[i] >= 0. and ratings[i] <= 1., 'rating out of range'
            self.ratings[i] += max(0, min(1, int(ratings[i])))
        self.rating_count += 1

    def encode_for_client(self, account_id: str, depth: int) -> Dict[str, Any]:
        # Give the post content to the client
        outgoing_packet: Dict[str, Any] = {
            'act': 'add',
            'id': self.id,
            'par': self.parent_id,
            'type': self.type,
            'text': self.text,
            'dep': depth,
        }

        # Give the client the author's picture and name
        if len(self.account_id) > 0:
            acc = account.account_cache[self.account_id]
            outgoing_packet['image'] = acc.image
            outgoing_packet['name'] = acc.name

        # Tell the client about any relevant whitelist
        if len(self.parent_id) > 0:
            par = post_cache[self.parent_id]
            if self.type == 'pod' and len(self.wl) > 0:
                if account_id in self.wl: # if the reader is in the whitelist...
                    pass
                elif len(self.wl) == 1:
                    outgoing_packet['ro'] = 1 # Allow accepting the debate challenge
                else:
                    outgoing_packet['ro'] = 2 # The user may read only
            elif par.type == 'pod' and len(par.wl) > 0:
                outgoing_packet['ind'] = par.wl.index(self.account_id) # Tell the client how to indent the post

        return outgoing_packet

    # Returns the mean aioff ratings and counts for a node
    def get_aioff_ratings(self) -> Tuple[List[float], int]:
        if self.rating_count > 0:
            assert self.ratings, 'expected ratings'
            mean = [ x / self.rating_count for x in self.ratings ]
        else:
            mean = [ 0. for _ in range(len(rec.rating_choices)) ]
        return mean, self.rating_count

def fetch_post(id: str) -> Post:
    return Post.unmarshal(id, db.get_post(id))

def store_post(id: str, post: Post) -> None:
    assert id == post.id, 'mismatching ids'
    db.put_post(id, post.marshal())

post_cache: cache.Cache[str,Post] = cache.Cache(1000, fetch_post, store_post)

# Makes a new post and inserts it into the tree
def new_post(id: str, parent_id: str, type: str, text: str, account_id: str) -> Post:
    op_id = ''
    if len(parent_id) > 0:
        par = post_cache[parent_id]
        assert not id in par.children
        par.children.append(id)
        post_cache.set_modified(parent_id)
        if par.type == 'op':
            op_id = parent_id
        else:
            op_id = par.op_id
    if type == 'rp' or type == 'pod':
        try:
            hist = history.history_cache[op_id]
        except KeyError:
            hist = history.history_cache.add(op_id, history.History())
        hist.on_post(id)
        history.history_cache.set_modified(op_id)
    return post_cache.add(id, Post(id, parent_id, op_id, type, text, account_id))
