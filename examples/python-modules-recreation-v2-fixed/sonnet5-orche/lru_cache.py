import threading
from collections import OrderedDict


class LRUCache:
    """Thread-safe LRU cache with configurable max size."""

    def __init__(self, max_size: int = 128):
        if max_size <= 0:
            raise ValueError("max_size must be a positive integer")
        self._max_size = max_size
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key, default=None):
        """Return the value for key, or default if not present.
        Marks the key as most recently used on a hit."""
        with self._lock:
            if key not in self._cache:
                return default
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key, value) -> None:
        """Insert or update key. Evicts the least recently used item
        if the cache exceeds max_size."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def delete(self, key) -> bool:
        """Remove key if present. Returns True if it was removed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key) -> bool:
        with self._lock:
            return key in self._cache