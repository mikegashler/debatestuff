from typing import Mapping, Dict, Any, List, Tuple
import cache
import accounts
from db import db
import webserver

class Session():
    def __init__(self, id: str, account_ids: List[str], active_index: int) -> None:
        self.id = id
        self.account_ids = account_ids
        self.active_index = active_index
        self.query: Mapping[str, Any] = {}

    # If account_name is the empty string, this will switch to the first account with no password, creating one if necessary
    def switch_account(self, account_name: str) -> None:
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
        else:
            acc = accounts.find_account_by_name(account_name)
            if acc.id in self.account_ids:
                self.active_index = self.account_ids.index(acc.id)
            else:
                self.active_index = len(self.account_ids)
                self.account_ids.append(acc.id)

    def marshal(self) -> Mapping[str, Any]:
        return {
            'accounts': self.account_ids,
            'active_index': self.active_index,
            'query': self.query,
        }

    @staticmethod
    def unmarshal(id: str, ob: Mapping[str, Any]) -> 'Session':
        sess = Session(id, ob['accounts'], ob['active_index'])
        sess.query = ob['query']
        return sess

    def active_account(self) -> accounts.Account:
        return accounts.account_cache[self.account_ids[self.active_index]]

def fetch_session(id: str) -> Session:
    return Session.unmarshal(id, db.get_session(id))

def store_session(id: str, sess: Session) -> None:
    assert id == sess.id, 'mismatching ids'
    db.put_session(id, sess.marshal())

session_cache: cache.Cache[str,Session] = cache.Cache(300, fetch_session, store_session)


def get_or_make_session(session_id: str) -> Session:
    try:
        return session_cache[session_id]
    except KeyError:
        _account = accounts.make_starter_account()
        session = Session(session_id, [ _account.id ], 0)
        session_cache.add(session_id, session)
        return session

# Make a session in advance for the next client who will need a new session
def reserve_session() -> Session:
    assert webserver.reserved_session is None, 'There is already a reserved session'
    webserver.reserved_session = webserver.new_session_id()
    return get_or_make_session(webserver.reserved_session)
