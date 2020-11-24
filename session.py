from typing import Mapping, Dict, Any, List, Tuple
import account

class Session():
    def __init__(self, accounts: List[account.Account], active_index: int) -> None:
        self.accounts = accounts
        self.active_account = self.accounts[active_index]

    # If account_name is the empty string, this will switch to the first account with no password, creating one if necessary
    def switch_account(self, account_name: str) -> None:
        if len(account_name) == 0:
            for i in range(len(self.accounts)):
                if len(self.accounts[i].password) == 0:
                    self.active_account = self.accounts[i]
                    return
            no_password_account = account.make_starter_account()
            self.accounts.append(no_password_account)
            self.active_account = no_password_account
        else:
            for i in range(len(self.accounts)):
                if self.accounts[i].name == account_name:
                    self.active_account = self.accounts[i]
                    return
            raise ValueError('No account named {account_name}')

    def marshal(self) -> Mapping[str, Any]:
        return {
            'accounts': [ x.marshal() for x in self.accounts ],
            'active_account': self.accounts.index(self.active_account),
        }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Session':
        return Session([ account.Account.unmarshal(x) for x in ob['accounts'] ], ob['active_account'])

sessions: Dict[str, Session] = {}

def get_session(session_id: str) -> Session:
    if session_id in sessions:
        return sessions[session_id]
    session = Session([ account.make_starter_account() ], 0)
    sessions[session_id] = session
    if len(sessions) == 1:
        session.accounts[0].admin = True
    return session
