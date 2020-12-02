from typing import Mapping, Any, List, Tuple
from db import db
import cache

class NotifIn():
    def __init__(self) -> None:
        self.notifs: List[Tuple[str, str, str]] = []

    def marshal(self) -> Mapping[str, Any]:
        return {
            'notifs': self.notifs,
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'NotifIn':
        notif_in = NotifIn()
        notif_in.notifs = ob['notifs']
        return notif_in


def fetch_notif_in(id: str) -> NotifIn:
    return NotifIn.unmarshal(db.get_notif_in(id))

def store_notif_in(id: str, notif_in: NotifIn) -> None:
    db.put_notif_in(id, notif_in.marshal())

notif_in_cache: cache.Cache[str,NotifIn] = cache.Cache(100, fetch_notif_in, store_notif_in)

def get_or_make_notif_in(account_id: str) -> NotifIn:
    try:
        return notif_in_cache[account_id]
    except KeyError:
        return notif_in_cache.add(account_id, NotifIn())








class NotifOut():
    def __init__(self) -> None:
        self.notifs: List[Tuple[str, str, str, str]] = []
        self.pos = 0

    def marshal(self) -> Mapping[str, Any]:
        return {
            'notifs': self.notifs,
            'pos': self.pos,
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'NotifOut':
        notif_out = NotifOut()
        notif_out.notifs = ob['notifs']
        notif_out.pos = ob['pos']
        return notif_out

def fetch_notif_out(id: str) -> NotifOut:
    return NotifOut.unmarshal(db.get_notif_out(id))

def store_notif_out(id: str, notif_out: NotifOut) -> None:
    db.put_notif_out(id, notif_out.marshal())

notif_out_cache: cache.Cache[str,NotifOut] = cache.Cache(100, fetch_notif_out, store_notif_out)




# Send a notification to the dest account
def notify(dest_account_id: str, type: str, post_id: str, src_account_id: str) -> None:
    try:
        notif_in = notif_in_cache[dest_account_id]
        notif_in_cache.set_modified(dest_account_id)
    except KeyError:
        notif_in = notif_in_cache.add(dest_account_id, NotifIn())
    assert len(notif_in.notifs) < 1000, 'Notifications are out of control!'
    notif_in.notifs.append((type, post_id, src_account_id))

# Extract a group of notifications that all have the same type and node id
def group_notifs(notif_in: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
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
def digest_notifications(account_id: str) -> List[Tuple[str, str, str, str]]:
    try:
        notif_in = notif_in_cache[account_id]
    except KeyError:
        notif_in = notif_in_cache.add(account_id, NotifIn())
    dirty = False
    try:
        notif_out = notif_out_cache[account_id]
    except KeyError:
        notif_out = notif_out_cache.add(account_id, NotifOut())
    notif_out.pos = len(notif_out.notifs)
    while len(notif_in.notifs) > 0:
        dirty = True
        while len(notif_out.notifs) >= 30:
            del notif_out.notifs[0]
            notif_out.pos = max(0, notif_out.pos - 1)
        group = group_notifs(notif_in.notifs)
        first = group[0]
        if len(first[2]) > 0:
            person = db.get_account(first[2])
            name = person['name']
            if len(group) == 2:
                person2 = db.get_account(group[1][2])
                name += f' and {person2["name"]}'
            elif len(group) > 2:
                name += f' and {len(group) - 1} others'
            notif_out.notifs.append((first[0], first[1], person['image'], name))
        else:
            name = f'{len(group)} {"person" if len(group) == 1 else "people"}'
            notif_out.notifs.append((first[0], first[1], 'starter_pics/rate.jpeg', name))
    if dirty:
        notif_in_cache.set_modified(account_id)
        notif_out_cache.set_modified(account_id)
    return notif_out.notifs
