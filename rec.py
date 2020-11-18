from typing import Tuple, Mapping, Any, Optional, List, Dict
import numpy as np
import tensorflow as tf
import nn
import random
import heapq
from datetime import datetime
import dateutil.parser # (When Python 3.7 becomes available, omit this line and use datetime.fromisoformat where needed)

rating_choices = [
    (1.,'Strong','Support for a position was given that would be difficult to attack'),
    (1.,'Interesting','A clever or novel point was made'),
    (1.,'Reasonable','An appropriate or suitable response was given'),
    (1.,'Eloquent','Clarity was elegantly woven with respectful articulation'),
    (-1.,'Impolite','Ad hominem, undignified, poisoning the well, rude, petulent, flippant, or attempt to shame'),
    (-1.,'Burden shifting','Asks others to disprove a non-obvious claim, "prove I\'m wrong"'),
    (-1.,'Preaching','A position was expressed without justification or supporting reasons, "trust me", threats, or condescending tone'),
    (-1.,'Anecdotal','Attempts to establish a trend from few examples, association fallacy, or leans on witnesses of extraordinary events'),
    (-1.,'Closed minded','Dismissive without a better alternative, appeals to ignorance, demands undeniable proof of the most plausible explanation'),
    (-1.,'Leaps','Jumps to desired conclusion from ambiguous data, circular reasoning, abandons assumptions, special pleading, or faulty analogy'),
    (-1.,'Straw-man','Battles a misrepresentation of an opponent\'s position, slippery slope, or tells opponent what they believe'),
    (-1.,'Word games','Supposes terms we define govern reality, ontological arguments, defines something into existence, proofs that work with anything'),
    (-1.,'Shirks','Appeals to popularity or authority or tradition or preference or celebrity quotes instead of offering reasons'),
    (-1.,'Is-ought','jumps from values to truth or reality to morality or argues from consequences, moralistic fallacy'),
    (-1.,'Vague conviction','Certain of something with a name but no clear definition, conflates naming with explaining, cherry picking'),
    (-1.,'Dumping','Attempts to overwhelm rather than convince, hides behind unsummarized canned content, Gish Gallop, excessively strong adjectives'),
    (-1.,'False choice','Presents an incomplete set of possibilities as complete, excluded middle fallacy, black or white thinking'),
    (-1.,'Unclear relevance','Miscategorized, off-topic, incoherent, word salad, or spam'),
]

rating_freq = [ 5 for _ in rating_choices ]
rating_count = 5 * len(rating_choices)

# Returns unbiased index, biased index, unbiased score, and biased score for a particular node and user.
def compute_scores(item_ratings_count: int, ur: List[float], br: List[float]) -> Tuple[int, int, float, float]:
    if item_ratings_count < 1:
        return 0, 0, 1000., 1000. # This item has never been rated
    assert len(ur) == len(rating_choices), f'unbiased ratings have unexpected size: {len(ur)}'
    assert len(br) == len(rating_choices), f'biased ratings have unexpected size: {len(br)} '
    max_unbiased_val = -1000000.
    max_unbiased_index = 0
    max_biased_val = -1000000.
    max_biased_index = 0
    unbiased_score = 0.
    biased_score = 0.
    for i in range(len(rating_choices)):
        # Unbiased
        unbiased_val = ur[i] # * rating_count / rating_freq[i]
        unbiased_score += unbiased_val * rating_choices[i][0]
        if unbiased_val > max_unbiased_val:
            max_unbiased_val = unbiased_val
            max_unbiased_index = i

        # Biased
        biased_val = br[i] # * rating_count / rating_freq[i]
        biased_score += biased_val * rating_choices[i][0]
        if biased_val > max_biased_val:
            max_biased_val = biased_val
            max_biased_index = i
    return max_unbiased_index, max_biased_index, unbiased_score, biased_score


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
    # role: -1=user, 0=neither, 1=item, 2=both
    def __init__(self, name: str, role: int) -> None:
        self.name = name
        self.values = np.random.normal(0., 0.01, [PROFILE_SIZE])
        self.role = role
        self.pairs: List[int] = []

    def set_role(self, role: int) -> None:
        if self.role == role or role == 0:
            return
        elif self.role == 0:
            self.role = role
        self.role = 2

    def marshal(self) -> Mapping[str, Any]:
        return {
                'id': self.name,
                'vals': self.values.tolist(),
                'role': self.role,
                'pairs': self.pairs,
            }

    @staticmethod
    def unmarshal(ob: Mapping[str, Any]) -> 'Profile':
        prof = Profile(ob['id'], ob['role'])
        prof.values = np.array(ob['vals'])
        prof.pairs = ob['pairs']
        return prof

class Engine:
    def __init__(self) -> None:
        self.model = Model()
        self.profiles: List[Profile] = []
        self.samples: List[Tuple[int, int, List[float]]] = [] # user_index, item_index, ratings
        self.str_to_profile_index: Dict[str, int] = {}

        # Buffers for batch training
        self.batch_users = np.empty([self.model.batch_size, PROFILE_SIZE], dtype=np.float32)
        self.batch_items = np.empty([self.model.batch_size, PROFILE_SIZE], dtype=np.float32)
        self.batch_ratings = np.empty([self.model.batch_size, len(rating_choices)], dtype=np.float32)

    def marshal(self) -> Mapping[str, Any]:
        return {
                'model': self.model.marshal(),
                'profiles': [ p.marshal() for p in self.profiles ],
                'samples': self.samples,
                'rating_freq': rating_freq,
                'rating_count': rating_count,
            }

    def unmarshal(self, ob: Mapping[str, Any]) -> None:
        self.model.unmarshal(ob['model'])
        self.profiles = []
        self.str_to_profile_index = {}
        for p in ob['profiles']:
            prof = Profile.unmarshal(p)
            self.str_to_profile_index[prof.name] = len(self.profiles)
            self.profiles.append(prof)
        self.samples = ob['samples']
        global rating_freq
        global rating_count
        rating_freq = ob['rating_freq']
        rating_count = ob['rating_count']

    # Input: name (or id string) for a profile
    # Output: The index and profile object associated with the id.
    #         (If no profile is associated with that id, one will be created.)
    def _get_profile(self, name: str, role: int) -> Tuple[int, Profile]:
        if name in self.str_to_profile_index:
            i = self.str_to_profile_index[name]
            p = self.profiles[i]
            p.set_role(role)
        else:
            i = len(self.profiles)
            p = Profile(name, role)
            self.profiles.append(p)
            self.str_to_profile_index[name] = i
        return i, p

    # Performs one batch of training on the pair model
    def _train_pairs(self, num_preferred: int = 0, preferred: List[int] = []) -> None:
        # Make a batch
        pair_indexes = []
        for i in range(self.batch_users.shape[0]):
            if i < num_preferred:
                index = preferred[random.randrange(len(preferred))]
            else:
                index = random.randrange(len(self.samples))
            pair_indexes.append(index)
            sample = self.samples[index]
            user_index = sample[0]
            item_index = sample[1]
            self.batch_users[i] = self.profiles[user_index].values
            self.batch_items[i] = self.profiles[item_index].values
            self.batch_ratings[i] = sample[2]

        # Refine
        self.model.set_users(self.batch_users)
        self.model.set_items(self.batch_items)
        self.model.refine(self.batch_ratings)

        # Store changes
        updated_users = self.model.batch_user.numpy()
        updated_items = self.model.batch_item.numpy()
        for i in range(len(pair_indexes)):
            index = pair_indexes[i]
            pair = self.samples[index]
            user_index = pair[0]
            item_index = pair[1]
            self.profiles[user_index].values = updated_users[i]
            self.profiles[item_index].values = updated_items[i]

    # Call this when a user expresses a rating for an item
    def rate(self, user: str, item: str, opinions:List[float]) -> None:
        i_user, p_user = self._get_profile(user, -1)
        i_item, p_item = self._get_profile(item, 1)
        i_pair = len(self.samples)
        self.samples.append((i_user, i_item, opinions)) # todo: what if this is stomping over an old rating?
        p_user.pairs.append(i_pair)
        p_item.pairs.append(i_pair)
        if len(self.samples) > 64:
            self._train_pairs()

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
            _, p_user = self._get_profile(users[i], -1)
            self.batch_users[j] = p_user.values
            _, p_item = self._get_profile(items[i], 1)
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
