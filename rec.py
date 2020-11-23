from typing import Tuple, Mapping, Any, Optional, List, Dict
import numpy as np
import tensorflow as tf
import nn
import random
import heapq
from datetime import datetime
import dateutil.parser # (When Python 3.7 becomes available, omit this line and use datetime.fromisoformat where needed)
from indexable_dict import IndexableDict

rating_choices = [
    (1.,'Strong','Support for a position was given that would be difficult to dismiss'),
    (1.,'Interesting','A clever or novel point was made'),
    (1.,'Reasonable','An appropriate, intelligent, or suitable response'),
    (1.,'Eloquent','A position was elegantly described with respectful articulation'),
    (-1.,'Impolite','Ad hominem, poisoning the well, rude, petulent, flippant, or attempt to shame'),
    (-1.,'Burden shifting','Asks others to disprove a non-obvious claim, "prove I\'m wrong"'),
    (-1.,'Preaching','A position was expressed without justification or supporting reasons, "trust me", threats, or condescending tone'),
    (-1.,'Anecdotal','Attempts to establish a trend from few examples, leans on witnesses for extraordinary events, or guilt by association'),
    (-1.,'Closed minded','Dismissive without a better alternative, appeals to ignorance, or assumes plausible explanation are false until proven true'),
    (-1.,'Leaps','Jumps to desired conclusion from ambiguous data, circular reasoning, abandons assumptions, special pleading, or faulty analogy'),
    (-1.,'Straw-man','Battles a misrepresentation of an opponent\'s position, slippery slope, or tells opponent what their position is'),
    (-1.,'Word games','Supposes terms we define govern reality, ontological arguments, defines something into existence, proofs that work with anything'),
    (-1.,'Shirks','Appeals to popularity or authority or celebrities or traditions or preferences instead of offering reasons'),
    (-1.,'Is-ought','jumps from values to truth or reality to morality or argues from consequences, moralistic fallacy'),
    (-1.,'Vague conviction','Certain of something with a name but no clear definition, conflates naming with explaining, or cherry picking'),
    (-1.,'Dumping','Attempts to overwhelm rather than convince, hides behind unsummarized canned content, Gish Gallop, or excessively strong adjectives'),
    (-1.,'False choice','Presents an incomplete set of possibilities as complete, excluded middle fallacy, black or white thinking'),
    (-1.,'Unclear relevance','Miscategorized, off-topic, incoherent, word salad, or spam'),
]

rating_freq = [ 5 for _ in rating_choices ]
rating_count = 5 * len(rating_choices)


PROFILE_SIZE = 12

class Model:
    def __init__(self) -> None:
        self.batch_size = 128
        self.batch_user = tf.Variable(np.zeros([self.batch_size, PROFILE_SIZE]), dtype = tf.float32)
        self.batch_item = tf.Variable(np.zeros([self.batch_size, PROFILE_SIZE]), dtype = tf.float32)
        self.common_layer = nn.LayerLinear(PROFILE_SIZE, len(rating_choices))
        self.optimizer = tf.keras.optimizers.SGD(learning_rate = 1e-5)
        self.params = self.common_layer.params

    def set_users(self, user_profiles: tf.Tensor) -> None:
        self.batch_user.assign(user_profiles)

    def set_items(self, item_profiles: tf.Tensor) -> None:
        self.batch_item.assign(item_profiles)

    def act(self) -> tf.Tensor:
        common = self.common_layer.act(self.batch_user * self.batch_item)
        return common

    def cost(self, targ: tf.Tensor, pred: tf.Tensor) -> tf.Tensor:
        return tf.reduce_mean(tf.reduce_sum(tf.square(targ - pred), axis = 1), axis = 0)

    def refine(self, y: tf.Tensor) -> None:
        self.optimizer.minimize(lambda: self.cost(y, self.act()), self.params)

    def marshal(self) -> Mapping[str, Any]:
        return {
                "params": [ p.numpy().tolist() for p in self.params ],
            }

    def unmarshal(self, ob: Mapping[str, Any]) -> None:
        params = ob['params']
        if len(params) != len(self.params):
            raise ValueError('Mismatching number of params')
        for i in range(len(params)):
            self.params[i].assign(np.array(params[i]))


class Profile:
    def __init__(self, id: str, vals:Optional[np.ndarray]=None) -> None:
        self.id = id
        if vals is None:
            self.values = np.random.normal(0., 0.01, [PROFILE_SIZE])
        else:
            assert vals.shape[0] == PROFILE_SIZE, 'unexpected profile size'
            self.values = vals

    def marshal(self) -> Mapping[str, Any]:
        return {
                'id': self.id,
                'vals': self.values.tolist(),
            }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Profile':
        return Profile(ob['id'], np.array(ob['vals']))


class Engine:
    def __init__(self) -> None:
        self.model = Model()
        self.user_profiles: IndexableDict[str, Profile] = IndexableDict()
        self.item_profiles: Dict[str, Profile] = {}

        # Buffers for batch training
        self.account_samplers = [ '' for i in range(12) ]
        self.account_index = 0
        self.batch_users = np.empty([self.model.batch_size, PROFILE_SIZE], dtype=np.float32)
        self.batch_items = np.empty([self.model.batch_size, PROFILE_SIZE], dtype=np.float32)
        self.batch_ratings = np.empty([self.model.batch_size, len(rating_choices)], dtype=np.float32)

    def marshal(self) -> Mapping[str, Any]:
        return {
                'model': self.model.marshal(),
                'user_profiles': { k:self.user_profiles[k].marshal() for k in self.user_profiles.to_dict() },
                'item_profiles': { k:self.item_profiles[k].marshal() for k in self.item_profiles },
                'rating_freq': rating_freq,
                'rating_count': rating_count,
            }

    def unmarshal(self, ob: Mapping[str, Any]) -> None:
        self.model.unmarshal(ob['model'])

        # User profiles
        self.user_profiles = IndexableDict()
        user_dict = ob['user_profiles']
        for k in user_dict:
            self.user_profiles[k] = Profile.unmarshal(user_dict[k])

        # item profiles
        self.item_profiles = {}
        item_dict = ob['item_profiles']
        for k in item_dict:
            self.item_profiles[k] = Profile.unmarshal(item_dict[k])

        global rating_freq
        global rating_count
        rating_freq = ob['rating_freq']
        rating_count = ob['rating_count']

    def prepare_rating_profiles(self, user_id: str, item_id: str) -> None:
        if not user_id in self.user_profiles:
            self.user_profiles[user_id] = Profile(user_id)
        if not item_id in self.item_profiles:
            self.item_profiles[item_id] = Profile(item_id)

    def _random_sample(self) -> Tuple[Profile, Profile, List[float]]:
        from account import find_account_by_id
        while True:
            if len(self.account_samplers[self.account_index]) == 0:
                self.account_samplers[self.account_index] = self.user_profiles.random_key()
                continue
            acc = find_account_by_id(self.account_samplers[self.account_index])
            weight = max(1, min(16, len(acc.ratings) / 4))
            if random.uniform(0, 1) < 1. / (1. + weight):
                self.account_samplers[self.account_index] = self.user_profiles.random_key()
                continue
            user_id = self.account_samplers[self.account_index]
            self.account_index = (self.account_index + 1) % len(self.account_samplers)
            item_id = acc.ratings.random_key()
            ratings = acc.ratings[item_id]
            return self.user_profiles[user_id], self.item_profiles[item_id], ratings

    # Performs one batch of training on the pair model
    def train(self) -> None:
        # Make a batch
        users: List[Profile] = []
        items: List[Profile] = []
        for i in range(self.batch_users.shape[0]):
            user, item, ratings = self._random_sample()
            users.append(user)
            items.append(item)
            self.batch_users[i] = user.values
            self.batch_items[i] = item.values
            self.batch_ratings[i] = ratings

        # Refine
        self.model.set_users(self.batch_users)
        self.model.set_items(self.batch_items)
        self.model.refine(self.batch_ratings)

        # Store changes
        updated_users = self.model.batch_user.numpy()
        updated_items = self.model.batch_item.numpy()
        for i in range(len(users)):
            users[i].values = updated_users[i]
            items[i].values = updated_items[i]

    # Assumes the profiles for the users and items already exist
    def predict(self, users:List[str], items:List[str]) -> List[List[float]]:
        assert len(users) == len(items), 'Expected lists to have same size'
        results: List[List[float]] = []
        if len(users) == 0:
            return results
        for i in range(len(users)):
            j = i % self.batch_users.shape[0]
            if j == 0 and i > 0:
                # Predict a batch
                self.model.set_users(self.batch_users)
                self.model.set_items(self.batch_items)
                pred = self.model.act().numpy()

                # Gather results
                for k in range(pred.shape[0]):
                    ratings = pred[k].tolist()
                    results.append(ratings)

            # Add to the batch
            p_user = self.user_profiles[users[i]]
            self.batch_users[j] = p_user.values
            p_item = self.item_profiles[items[i]]
            self.batch_items[j] = p_item.values

        # Predict the final batch
        self.model.set_users(self.batch_users)
        self.model.set_items(self.batch_items)
        pred = self.model.act().numpy()

        # Gather results
        remainder = len(users) % self.batch_users.shape[0]
        if remainder == 0:
            remainder = self.batch_users.shape[0]
        for k in range(remainder):
            ratings = pred[k].tolist()
            results.append(ratings)
        return results

engine = Engine()
