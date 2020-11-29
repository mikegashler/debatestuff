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
        pass
        # if len(account_name) == 0:
        #     for i in range(len(self.accounts)):
        #         if len(self.accounts[i].password) == 0:
        #             self.active_account = self.accounts[i]
        #             return
        #     no_password_account = account.make_starter_account()
        #     self.accounts.append(no_password_account)
        #     self.active_account = no_password_account
        # else:
        #     for i in range(len(self.account_ids)):
        #         if self.accounts[i].name == account_name:
        #             self.active_account = self.accounts[i]
        #             return
        #     raise ValueError('No account named {account_name}')

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
