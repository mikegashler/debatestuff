from typing import TypeVar, Generic, Dict, List, Mapping, Any
import random

K = TypeVar('K')
V = TypeVar('V')
class IndexableDict(Generic[K, V]):
    def __init__(self) -> None:
        self._keys: List[K] = []
        self._vals: List[V] = []
        self.dict: Dict[K, int] = {}

    def __getitem__(self, key: K) -> V:
        return self._vals[self.dict[key]]

    def __setitem__(self, key: K, val: V) -> None:
        if key in self.dict:
            index = self.dict[key]
            self._vals[index] = val
        else:
            self.dict[key] = len(self._keys)
            self._keys.append(key)
            self._vals.append(val)

    def __contains__(self, key: K) -> bool:
        return key in self.dict

    def __len__(self) -> int:
        return len(self._keys)

    def keys(self) -> List[K]:
        return self._keys

    def vals(self) -> List[V]:
        return self._vals

    def to_dict(self) -> Dict[K, V]:
        return { k:v for k,v in zip(self._keys, self._vals) }

    def random_key(self) -> K:
        assert len(self._keys) > 0, 'No keys to choose from'
        return self._keys[random.randrange(len(self._keys))]

    def marshal(self) -> Mapping[K, V]:
        return {
            self._keys[i]: (self._vals[i] if isinstance(self._vals[i], list) else self._vals[i].marshal()) # type: ignore
            for i in range(len(self._keys))
        }

    @staticmethod
    def unmarshal(ob: Mapping[K, V]) -> "IndexableDict[K,V]":
        id:"IndexableDict[K,V]" = IndexableDict()
        for key in ob.keys():
            id[key] = ob[key]
        return id
