from typing import Mapping, Dict, Any, List, Tuple
import cache
import account
from db import db

class Session():
    def __init__(self, id: str, account_ids: List[str], active_index: int) -> None:
        self.id = id
        self.account_ids = account_ids
        self.active_index = active_index

    # If account_name is the empty string, this will switch to the first account with no password, creating one if necessary
    def switch_account(self, account_name: str) -> None:
        session_cache.set_modified(self.id)
        if len(account_name) == 0: # Log out
            for i in range(len(self.account_ids)):
                acc_id = self.account_ids[i]
                acc = account.account_cache[acc_id]
                if len(acc.password) == 0:
                    assert self.active_account != i, 'Log out should not be an option for accounts with no password'
                    self.active_index = i
                    return
            no_password_account = account.make_starter_account()
            self.active_index = len(self.account_ids)
            self.account_ids.append(no_password_account.id)
        else:
            acc = account.find_account_by_name(account_name)
            if acc.id in self.account_ids:
                self.active_index = self.account_ids.index(acc.id)
            else:
                self.active_index = len(self.account_ids)
                self.account_ids.append(acc.id)

    def marshal(self) -> Mapping[str, Any]:
        return {
            'accounts': self.account_ids,
            'active_index': self.active_index,
        }

    @staticmethod
    def unmarshal(id: str, ob: Mapping[str, Any]) -> 'Session':
        return Session(id, ob['accounts'], ob['active_index'])

    def active_account(self) -> account.Account:
        return account.account_cache[self.account_ids[self.active_index]]

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
        _account = account.make_starter_account()
        session = Session(session_id, [ _account.id ], 0)
        session_cache[session_id] = session
        # if len(sessions) == 1:
        #     session.accounts[0].admin = True
        return session
