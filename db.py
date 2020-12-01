from typing import Optional, Dict, Mapping, Any, List, Tuple, cast
import pymongo
import json
import os
from indexable_dict import IndexableDict

def bootstrap() -> None:
    import posts
    root = posts.new_post('000000000000', '', 'cat', 'Everything', '')
    posts.new_post(posts.new_post_id(), root.id, 'cat', 'Politics', '')
    posts.new_post(posts.new_post_id(), root.id, 'cat', 'STEM', '')
    posts.new_post(posts.new_post_id(), root.id, 'cat', 'Entertainment', '')
    posts.new_post(posts.new_post_id(), root.id, 'cat', 'Theology', '')
    posts.new_post(posts.new_post_id(), root.id, 'cat', 'Miscellaneous', '')

def flush_caches() -> None:
    import account
    import session
    import posts
    import history
    account.account_cache.flush()
    session.session_cache.flush()
    posts.post_cache.flush()
    history.history_cache.flush()

# An in-memory "database" that periodically writes to a flat file
class FlatFile():
    def __init__(self) -> None:
        self.sessions: Dict[str, Mapping[str, Any]] = {}
        self.accounts: Dict[str, Mapping[str, Any]] = {}
        self.notif_in: Dict[str, Mapping[str, Any]] = {}
        self.notif_out: Dict[str, Mapping[str, Any]] = {}
        self.posts: Dict[str, Mapping[str, Any]] = {}
        self.history: Dict[str, Mapping[str, Any]] = {}
        self.ratings: IndexableDict[str, List[float]] = IndexableDict()

    # Save all the data to a flat file
    def save(self) -> None:
        flush_caches()
        packet = {
            'sessions': self.sessions,
            'accounts': self.accounts,
            'notif_in': self.notif_in,
            'notif_out': self.notif_out,
            'posts': self.posts,
            'history': self.history,
            'ratings': self.ratings.to_mapping(),
            # 'tree': feed.root.marshal(),
            # 'engine': rec.engine.marshal(),
        }

        # Write to file
        blob = bytes(json.dumps(packet), 'utf8')
        with open('state.json', mode='wb+') as file:
            file.write(blob)

    # Load all the data from a flat file
    def load(self) -> None:
        if not os.path.exists('state.json'):
            bootstrap()
        else:
            # Parse the file
            blob = None
            with open('state.json', mode='rb') as file:
                blob = file.read()
            packet = json.loads(blob)
            self.sessions = packet['sessions']
            self.accounts = packet['accounts']
            self.notif_in = packet['notif_in']
            self.notif_out = packet['notif_out']
            self.posts = packet['posts']
            self.history = packet['history']
            self.ratings = IndexableDict.from_mapping(packet['ratings'])

            # # Load the recommender engine
            # rec.engine.unmarshal(packet['engine'])

    # Consumes a marshaled session object (including its own '_id' field)
    def put_session(self, id: str, session: Mapping[str, Any]) -> None:
        self.sessions[id] = session

    # Consumes a session id
    # Returns a marshaled session object
    def get_session(self, id: str) -> Mapping[str, Any]:
        return self.sessions[id]

    # Consumes a marshaled account object (including its own '_id' field)
    def put_account(self, id: str, account: Mapping[str, Any]) -> None:
        self.accounts[id] = account

    # Consumes an account id
    # Returns a marshaled account
    def get_account(self, id: str) -> Mapping[str, Any]:
        return self.accounts[id]

    # Consumes an account name
    # Returns a marshaled account with that name if one exists
    def get_account_by_name(self, name: str) -> Mapping[str, Any]:
        for id in self.accounts.keys():
            account = self.accounts[id]
            if account['name'] == name:
                return account
        raise KeyError(name)

    # Consumes an account id and a list of notifications
    def put_notif_in(self, account_id: str, doc: Mapping[str, Any]) -> None:
        self.notif_in[account_id] = doc

    # Consumes an account id
    # Returns a list of notifications
    def get_notif_in(self, account_id: str) -> Mapping[str, Any]:
        return self.notif_in[account_id]

    # Consumes an account id and a list of notifications
    def put_notif_out(self, account_id: str, doc: Mapping[str, Any]) -> None:
        self.notif_out[account_id] = doc

    # Consumes an account id
    # Returns a list of notifications
    def get_notif_out(self, account_id: str) -> Mapping[str, Any]:
        return self.notif_out[account_id]

    # Consumes a marshaled post object (including its own '_id' field)
    def put_post(self, id: str, doc: Mapping[str, Any]) -> None:
        self.posts[id] = doc

    # Consumes a post id
    # Returns a marshaled post object
    def get_post(self, id: str) -> Mapping[str, Any]:
        return self.posts[id]

    # Consumes a history object (including its own '_id' field for the OP post)
    def put_history(self, id: str, doc: Mapping[str, Any]) -> None:
        self.history[id] = doc

    # Consumes a post id for the OP
    # Returns a history object
    def get_history(self, id: str) -> Mapping[str, Any]:
        return self.history[id]

    # Consumes an account id, a post id, and ratings for the pair
    def put_rating(self, user: str, item: str, vals: List[float]) -> None:
        self.ratings[f'{user},{item}'] = vals

    # # Updates a batch of ratings
    # def update_ratings(self, batch: List[Tuple[str, str, List[float]]]) -> None:
    #     for rating in batch:
    #         self.put_rating(rating[0], rating[1], rating[2])

    # Consumes an account id and a post id
    # Returns ratings for a user-item (account-post) pair
    def get_rating(self, user: str, item: str) -> List[float]:
        return self.ratings[f'{user},{item}']

    # Consumes an account id and a list of post ids
    # Returns a mapping of item ids that have ratings to the corresponding ratings
    # Items that have not been rated will not be included in the results
    def get_ratings_for_rated_items(self, user: str, item_list: List[str]) -> Mapping[str, List[float]]:
        results: Dict[str, Any] = {}
        for item in item_list:
            key = f'{user},{item}'
            if key in self.ratings:
                results[key] = self.ratings[key]
        return results

    # Consumes a number of samples
    # Returns that number of random [user_id, item_id, ratings] tuples
    def get_random_ratings(self, n: int) -> List[Tuple[str, str, List[float]]]:
        results: List[Tuple[str, str, List[float]]] = []
        for i in range(n):
            key = self.ratings.random_key()
            first_comma = key.index(',')
            assert first_comma >= 0, 'malformed key'
            results.append((key[:first_comma], key[first_comma+1:], self.ratings[key]))
        return results





# A Mongo database
class Mongo():
    client: Optional[pymongo.MongoClient] = None

    def __init__(self) -> None:
        if Mongo.client is None:
            Mongo.client = pymongo.MongoClient('mongodb://localhost:27016/')
        self.db = Mongo.client['debatestuff']
        self.sessions = self.db['sessions']
        self.accounts = self.db['accounts']
        self.notif_in = self.db['notif_in']
        self.notif_out = self.db['notif_out']
        self.posts = self.db['posts']
        self.history = self.db['history']
        self.ratings = self.db['ratings']

    def save(self) -> None:
        flush_caches()

    def load(self) -> None:
        if self.posts.count() == 0:
            bootstrap()

    # Consumes a marshaled session object (including its own '_id' field)
    def put_session(self, id: str, doc: Mapping[str, Any]) -> None:
        self.sessions.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes a session id
    # Returns a marshaled session object
    def get_session(self, id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.sessions.find_one({'_id': id})
        if doc is None:
            raise KeyError(id)
        return doc

    # Consumes a marshaled account object (including its own '_id' field)
    def put_account(self, id: str, doc: Mapping[str, Any]) -> None:
        self.accounts.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes an account id
    # Returns a marshaled account
    def get_account(self, id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.accounts.find_one({'_id': id})
        if doc is None:
            raise KeyError(id)
        return doc

    # Consumes an account name
    # Returns a marshaled account with that name if one exists
    def get_account_by_name(self, name: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.accounts.find_one({'name': name})
        if doc is None:
            raise KeyError(name)
        return doc

    # Consumes an account id and a list of notifications
    def put_notif_in(self, id: str, doc: Mapping[str, Any]) -> None:
        self.notif_in.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes an account id
    # Returns a list of notifications
    def get_notif_in(self, account_id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.notif_in.find_one({'_id': account_id})
        if doc is None:
            raise KeyError(account_id)
        return doc

    # Consumes an account id and a list of notifications
    def put_notif_out(self, id: str, doc: Mapping[str, Any]) -> None:
        self.notif_out.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes an account id
    # Returns a list of notifications
    def get_notif_out(self, account_id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.notif_out.find_one({'_id': account_id})
        if doc is None:
            raise KeyError(account_id)
        return doc

    # Consumes a marshaled session object (including its own '_id' field)
    def put_post(self, id: str, doc: Mapping[str, Any]) -> None:
        self.posts.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes a post id
    # Returns a marshaled session object
    def get_post(self, id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.posts.find_one({'_id': id})
        if doc is None:
            raise KeyError(id)
        return doc

    # Consumes a history object (including its own '_id' field for the OP)
    def put_history(self, id: str, doc: Mapping[str, Any]) -> None:
        self.history.replace_one(
            {'_id': id},
            doc,
            upsert=True,
        )

    # Consumes a post id for the OP
    # Returns a marshaled history object
    def get_history(self, id: str) -> Mapping[str, Any]:
        doc: Optional[Mapping[str, Any]] = self.history.find_one({'_id': id})
        if doc is None:
            raise KeyError(id)
        return doc

    # Consumes an account id, a post id, and ratings for the pair
    def put_rating(self, user_id: str, item_id: str, vals: List[float]) -> None:
        self.ratings.replace_one(
            {'_id': f'{user_id},{item_id}'},
            {
                'user': user_id,
                'item': item_id,
                'vals': vals,
            },
            upsert=True,
        )

    # # Updates a batch of ratings
    # def update_ratings(self, batch: List[Tuple[str, str, List[float]]]) -> None:
    #     operations = [
    #         pymongo.UpdateOne(
    #             {'_id': f'{rating[0]},{rating[1]}'},
    #             {'$set':
    #                 {
    #                     'user': rating[0],
    #                     'item': rating[1],
    #                     'vals': rating[2],
    #                 }
    #             },
    #             upsert=True,
    #         )
    #         for rating in batch
    #     ]
    #     self.ratings.bulk_write(operations)

    # Consumes an account id and a post id
    # Returns ratings for a user-item (account-post) pair
    def get_rating(self, user: str, item: str) -> List[float]:
        doc: Optional[Mapping[str, Any]] = self.ratings.find_one({'user': user, 'item': item})
        if doc is None:
            raise KeyError(f'{user},{item}')
        return cast(List[float], doc['vals'])

    # Consumes an account id and a list of post ids
    # Returns a mapping of item ids that have ratings to the corresponding ratings
    # Items that have not been rated will not be included in the results
    def get_ratings_for_rated_items(self, user: str, item_list: List[str]) -> Mapping[str, List[float]]:
        cursor = self.ratings.find({'user': user, 'item': {'$in': item_list}})
        return { doc['item']: doc['vals'] for doc in cursor }

    # Consumes a number of samples
    # Returns that number of random [user_id, item_id, ratings] tuples
    def get_random_ratings(self, n: int) -> List[Tuple[str, str, List[float]]]:
        cursor = self.ratings.aggregate([{'$sample': { 'size': n }}])
        return [ (doc['user'], doc['item'], doc['vals']) for doc in cursor ]


# db = FlatFile()
db = Mongo()
