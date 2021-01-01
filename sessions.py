from typing import Mapping, Dict, Any, List, Tuple, Optional
import cache
from db import db
import random
import string
import rec

COOKIE_LEN = 12

reserved_session: Optional[str] = None

def new_session_id() -> str:
    global reserved_session
    if reserved_session is not None:
        sess_id, reserved_session = reserved_session, None
        return sess_id
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(COOKIE_LEN))


class Session():
    def __init__(self, id: str, account_ids: List[str], active_index: int) -> None:
        self.id = id
        self.account_ids = account_ids
        self.active_index = active_index
        self.query: Mapping[str, Any] = {}
        self.addr = ''
        self.banned = False

    # If account_name is the empty string, this will switch to the first account with no password, creating one if necessary
    def switch_account(self, account_name: str, password: str) -> None:
        import accounts
        session_cache.set_modified(self.id)
        if len(account_name) == 0: # Log out
            for i in range(len(self.account_ids)):
                acc_id = self.account_ids[i]
                acc = accounts.account_cache[acc_id]
                if len(acc.password) == 0:
                    assert self.active_index != i, 'Log out should not be an option for accounts with no password'
                    self.active_index = i
                    return
            no_password_account = accounts.make_starter_account()
            self.active_index = len(self.account_ids)
            self.account_ids.append(no_password_account.id)
            no_password_account.session_id = self.id
        else:
            acc = accounts.find_account_by_name(account_name)
            if acc.password != password:
                raise ValueError('Incorrect password')
            if acc.banned:
                rec.engine.banned_addresses.add(self.addr)
                raise ValueError('Log in to banned account')
            if acc.id in self.account_ids:
                self.active_index = self.account_ids.index(acc.id)
            else:
                self.active_index = len(self.account_ids)
                self.account_ids.append(acc.id)
                acc.session_id = self.id

    def marshal(self) -> Mapping[str, Any]:
        return {
            'accounts': self.account_ids,
            'active_index': self.active_index,
            'query': self.query,
            'addr': self.addr,
            'banned': self.banned,
        }

    @staticmethod
    def unmarshal(id: str, ob: Mapping[str, Any]) -> 'Session':
        sess = Session(id, ob['accounts'], ob['active_index'])
        sess.query = ob['query']
        sess.addr = ob['addr']
        sess.banned = ob['banned']
        return sess

def fetch_session(id: str) -> Session:
    return Session.unmarshal(id, db.get_session(id))

def store_session(id: str, sess: Session) -> None:
    assert id == sess.id, 'mismatching ids'
    db.put_session(id, sess.marshal())

session_cache: cache.Cache[str,Session] = cache.Cache(300, fetch_session, store_session)


def get_or_make_session(session_id: str, ip_address: str) -> Session:
    import accounts
    if ip_address in rec.engine.banned_addresses:
        raise ValueError('Banned address')
    try:
        session = session_cache[session_id]
        if session.banned:
            rec.engine.banned_addresses.add(ip_address)
            raise ValueError('Banned session')
    except KeyError:
        account = accounts.make_starter_account()
        session = Session(session_id, [ account.id ], 0)
        session_cache.add(session_id, session)
    if len(ip_address) > 0:
        session.addr = ip_address
    return session

# Make a session in advance for the next client who will need a new session
def reserve_session() -> Session:
    global reserved_session
    assert reserved_session is None, 'There is already a reserved session'
    reserved_session = new_session_id()
    return get_or_make_session(reserved_session, '')
