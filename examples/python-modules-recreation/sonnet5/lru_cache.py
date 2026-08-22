"""A thread-safe LRU (Least Recently Used) cache.

Pure standard-library implementation backed by ``collections.OrderedDict``
and guarded by a single lock, so every public method is safe to call from
multiple threads concurrently.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Generic, Optional, TypeVar

K = TypeVar("K")
V = TypeVar("V")

_MISSING = object()


class LRUCache(Generic[K, V]):
    """A fixed-capacity cache that evicts the least recently used entry."""

    def __init__(self, max_size: int = 128) -> None:
        if not isinstance(max_size, int) or max_size <= 0:
            raise ValueError("max_size must be a positive integer")
        self._max_size = max_size
        self._data: "OrderedDict[K, V]" = OrderedDict()
        self._lock = threading.Lock()

    @property
    def max_size(self) -> int:
        return self._max_size

    def get(self, key: K, default: Optional[V] = None) -> Optional[V]:
        """Return the value for ``key``, marking it most recently used.

        Returns ``default`` (``None`` unless overridden) if the key is
        not present, without affecting recency order.
        """
        with self._lock:
            value = self._data.get(key, _MISSING)
            if value is _MISSING:
                return default
            self._data.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        """Insert or update ``key``, marking it most recently used.

        If the cache is over capacity after the insert, the least
        recently used entry is evicted.
        """
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def __contains__(self, key: K) -> bool:
        with self._lock:
            return key in self._data

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __repr__(self) -> str:
        with self._lock:
            return f"LRUCache(size={len(self._data)}, max_size={self._max_size})"
