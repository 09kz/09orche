"""Thread-safe LRU (Least Recently Used) cache implementation.

This module provides :class:`LRUCache`, a fixed-capacity key-value cache
that evicts the least recently used entry when the capacity is exceeded.
All operations are guarded by a lock, making the cache safe for use from
multiple threads.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Hashable


class LRUCache:
    """A thread-safe LRU cache with a fixed maximum size.

    Args:
        max_size: Maximum number of entries the cache may hold. Must be a
            positive integer.

    Raises:
        ValueError: If ``max_size`` is not a positive integer.
    """

    def __init__(self, max_size: int) -> None:
        if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size <= 0:
            raise ValueError("max_size must be a positive integer")
        self._max_size = max_size
        self._data: "OrderedDict[Hashable, Any]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Return the value for ``key``, or ``default`` if not present.

        A successful lookup marks ``key`` as most recently used. This method
        never raises for missing keys.

        Args:
            key: The key to look up.
            default: Value returned when ``key`` is absent.

        Returns:
            The cached value or ``default``.
        """
        with self._lock:
            try:
                value = self._data[key]
            except KeyError:
                return default
            self._data.move_to_end(key)
            return value

    def put(self, key: Hashable, value: Any) -> None:
        """Insert or update ``key`` with ``value``, marking it most recently used.

        If inserting a new key would exceed ``max_size``, the least recently
        used entry is evicted first.

        Args:
            key: The key to insert or update.
            value: The value to associate with ``key``.
        """
        with self._lock:
            if key in self._data:
                self._data[key] = value
                self._data.move_to_end(key)
                return
            if len(self._data) >= self._max_size:
                self._data.popitem(last=False)
            self._data[key] = value

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        """Return the number of entries currently in the cache."""
        with self._lock:
            return len(self._data)

    def __contains__(self, key: object) -> bool:
        """Return whether ``key`` is present in the cache.

        Note: membership testing does not affect recency order.
        """
        with self._lock:
            return key in self._data
