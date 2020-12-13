from typing import TypeVar, Generic, Callable, Set
from indexable_dict import IndexableDict

K = TypeVar('K')
V = TypeVar('V')

# A cache for wrapping a database collection.
# Holds up to max_size objects in memory.
# Releases random objects when the cache gets too full.
# Only writes objects back to the database for which set_modified has been called.
class Cache(Generic[K,V]):
    def __init__(self, max_size: int, get_func: Callable[[K],V], put_func: Callable[[K,V],None]) -> None:
        self.max_size = max_size
        self.get_func = get_func
        self.put_func = put_func
        self.cache: IndexableDict[K,V] = IndexableDict()
        self.modified: Set[K] = set()

    # This returns true iff the cache contains the key.
    # If you want to know whether the database collection contains the key,
    # you should call __getitem__ within a "try: / except KeyError:" block
    def __contains__(self, key: K) -> bool:
        return key in self.cache

    # Returns the number of items in the cache, not in the database collection
    def __len__(self) -> int:
        return len(self.cache)

    # Flags an item to be written to the database when it is released
    def set_modified(self, key: K) -> None:
        self.modified.add(key)

    # Returns true iff this item has been flagged as modified
    def has_been_modified(self, key: K) -> bool:
        return key in self.modified

    # Writes to the database if the item has been modified,
    # then removes it from this cache
    def release(self, key: K) -> None:
        if self.has_been_modified(key):
            self.put_func(key, self.cache[key])
        self.cache.drop(key)

    # Releases items until this cache is empty
    def flush(self) -> None:
        while len(self.cache) > 0:
            self.release(self.cache.random_key())

    # Retrieves the specified item. Hits the database only if necessary.
    def __getitem__(self, key: K) -> V:
        if key in self.cache:
            return self.cache[key]
        val = self.get_func(key)
        self[key] = val
        return val

    # Stores the specified item in this cache. Releases a random item if necessary to keep the cache size limited.
    def __setitem__(self, key: K, val: V) -> None:
        if len(self.cache) >= self.max_size:
            self.release(self.cache.random_key())
        self.cache[key] = val

    # A convenience method that: (1) adds a key-val pair to the cache, (2) flags it as modified, and (3) returns val
    def add(self, key: K, val: V) -> V:
        self[key] = val
        self.set_modified(key)
        return val
