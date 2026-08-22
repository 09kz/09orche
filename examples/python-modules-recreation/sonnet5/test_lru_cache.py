import threading

import pytest

from lru_cache import LRUCache


def test_put_get_basic():
    cache = LRUCache(max_size=3)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_get_missing_key_returns_default():
    cache = LRUCache(max_size=2)
    assert cache.get("missing") is None
    assert cache.get("missing", "fallback") == "fallback"


def test_len_and_contains():
    cache = LRUCache(max_size=2)
    assert len(cache) == 0
    cache.put("a", 1)
    assert len(cache) == 1
    assert "a" in cache
    assert "b" not in cache


def test_update_existing_key_overwrites_value_and_does_not_grow():
    cache = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("a", 2)
    assert len(cache) == 1
    assert cache.get("a") == 2


def test_invalid_max_size_raises():
    with pytest.raises(ValueError):
        LRUCache(max_size=0)
    with pytest.raises(ValueError):
        LRUCache(max_size=-1)


def test_clear_removes_all_entries():
    cache = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.clear()
    assert len(cache) == 0
    assert "a" not in cache


# -- Eviction order -----------------------------------------------------


def test_evicts_least_recently_inserted_when_full():
    cache = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)  # evicts "a", the least recently used
    assert "a" not in cache
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_get_promotes_key_to_most_recently_used():
    cache = LRUCache(max_size=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    cache.get("a")  # order is now: b, c, a
    cache.put("d", 4)  # evicts "b", the new least recently used

    assert "b" not in cache
    assert set().union(k for k in ("a", "c", "d") if k in cache) == {"a", "c", "d"}


def test_put_on_existing_key_promotes_to_most_recently_used():
    cache = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)  # order is now: b, a
    cache.put("c", 3)  # evicts "b"

    assert "b" not in cache
    assert cache.get("a") == 10
    assert cache.get("c") == 3


def test_full_eviction_sequence_matches_lru_order():
    cache = LRUCache(max_size=3)
    for key in ["a", "b", "c", "d", "e"]:
        cache.put(key, key.upper())

    # Only the last 3 inserted keys should remain.
    assert set(k for k in ["a", "b", "c", "d", "e"] if k in cache) == {"c", "d", "e"}
    assert len(cache) == 3


# -- Thread safety --------------------------------------------------------


def test_thread_safety_concurrent_put_get_no_errors():
    cache = LRUCache(max_size=50)
    errors = []

    def worker(thread_id):
        try:
            for i in range(500):
                key = f"{thread_id}-{i % 20}"
                cache.put(key, i)
                cache.get(key)
                cache.get("nonexistent-key")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(cache) <= cache.max_size


def test_thread_safety_never_exceeds_max_size_under_contention():
    max_size = 10
    cache = LRUCache(max_size=max_size)
    start_barrier = threading.Barrier(16)

    def worker(thread_id):
        start_barrier.wait()
        for i in range(200):
            cache.put(f"{thread_id}-{i}", i)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(cache) == max_size


def test_thread_safety_same_keys_hammered_by_many_threads():
    cache = LRUCache(max_size=5)
    keys = [f"key-{i}" for i in range(5)]
    errors = []

    def worker(thread_id):
        try:
            for i in range(1000):
                key = keys[i % len(keys)]
                cache.put(key, thread_id)
                cache.get(key)
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    # Same 5 keys are reused by every thread, so no eviction should occur.
    assert len(cache) == 5
    for key in keys:
        assert key in cache
