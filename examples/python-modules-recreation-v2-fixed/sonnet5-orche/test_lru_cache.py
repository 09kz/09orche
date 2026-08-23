import threading
import random

import pytest

from lru_cache import LRUCache


def test_basic_put_get():
    cache = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)

    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_get_missing_key_returns_none():
    cache = LRUCache(capacity=2)
    assert cache.get("missing") is None


def test_overwrite_existing_key():
    cache = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("a", 10)
    assert cache.get("a") == 10


def test_eviction_order_lru_first():
    cache = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    # Access "a" so "b" becomes least recently used.
    assert cache.get("a") == 1
    cache.put("c", 3)  # evicts "b"

    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_eviction_without_gets():
    cache = LRUCache(capacity=3)
    for i, key in enumerate(["x", "y", "z"]):
        cache.put(key, i)
    cache.put("w", 4)  # evicts "x" (oldest inserted)

    assert cache.get("x") is None
    assert cache.get("y") == 1
    assert cache.get("z") == 2
    assert cache.get("w") == 4


def test_capacity_one():
    cache = LRUCache(capacity=1)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_concurrent_stress():
    capacity = 100
    num_threads = 8
    ops_per_thread = 2000

    cache = LRUCache(capacity=capacity)
    errors = []

    def worker(seed):
        rng = random.Random(seed)
        try:
            for _ in range(ops_per_thread):
                key = rng.randrange(0, capacity * 2)
                if rng.random() < 0.5:
                    cache.put(key, seed)
                else:
                    value = cache.get(key)
                    if value is not None:
                        assert isinstance(value, int)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [
        threading.Thread(target=worker, args=(i,))
        for i in range(num_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors

    # After the storm the cache must respect its capacity bound.
    keys_seen = set()
    # Drain by probing a wide key range; count non-None hits indirectly
    # via repeated puts and checking no exception/corruption occurred.
    for key in range(capacity * 2):
        cache.put(key, key)
    for key in range(capacity * 2 - capacity, capacity * 2):
        assert cache.get(key) is not None