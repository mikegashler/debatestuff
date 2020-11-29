from typing import Mapping, Any, List, Dict, Tuple
from db import db
import cache

class History():
    def __init__(self) -> None:
        self.start = 0
        self.posts: List[str] = []

    def marshal(self) -> Mapping[str, Any]:
        return {
            'start': self.start,
            'posts': self.posts,
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'History':
        hist = History()
        hist.start = ob['start']
        hist.posts = ob['posts']
        return hist

    # Returns the number of revisions
    def revs(self) -> int:
        return self.start + len(self.posts)

    # Returns the post id for the specified revision number
    def get_rev(self, i: int) -> str:
        return self.posts[i - self.start]

    def on_post(self, id: str) -> None:
        self.posts.append(id)

    def rewrite_history_recursive(self, post_id: str) -> None:
        import posts
        post = posts.post_cache[post_id]
        for c in post.children:
            self.on_post(c)
            self.rewrite_history_recursive(c)

def fetch_history(id: str) -> History:
    return History.unmarshal(db.get_history(id))

def store_history(id: str, hist: History) -> None:
    db.put_history(id, hist.marshal())

history_cache: cache.Cache[str,History] = cache.Cache(100, fetch_history, store_history)


# Reconstruct the history of an OP so that changes to an existing node will be received.
# (Note: This will cause everyone to download the OP and all its children again.)
def rewrite_op_history(op_id: str) -> None:
    hist = history_cache[op_id]
    hist.start = len(hist.posts)
    hist.posts = []
    hist.rewrite_history_recursive(op_id)
