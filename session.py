from typing import Mapping, Dict, Any, List, Tuple
import account
from db import db

session_cache: Dict[str, "Session"] = {}

class Session():
    def __init__(self, id: str, account_ids: List[str], active_index: int) -> None:
        self.id = id
        self.account_ids = account_ids
        self.active_index = active_index
        global session_cache
        if len(session_cache) > 500:
            session_cache = {} # Periodically flush the cache so it doesn't get bloated
        session_cache[id] = self

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
            '_id': self.id,
            'accounts': self.account_ids,
            'active_index': self.active_index,
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Session':
        return Session(ob['_id'], ob['accounts'], ob['active_index'])

    def active_account(self) -> account.Account:
        return account.find_account_by_id(self.account_ids[self.active_index])

def get_or_make_session(session_id: str) -> Session:
    if session_id in session_cache:
        return session_cache[session_id]
    try:
        packet = db.get_session(session_id)
        return Session.unmarshal(packet)
    except KeyError:
        _account = account.make_starter_account()
        session = Session(session_id, [ _account.id ], 0)
        db.put_session(session.marshal())
        # if len(sessions) == 1:
        #     session.accounts[0].admin = True
    return session
