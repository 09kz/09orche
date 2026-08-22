"""Test suite for lru_cache.LRUCache."""

import threading

import pytest

from lru_cache import LRUCache


class TestBasicGetPut:
    def test_put_then_get(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        assert cache.get("a") == 1

    def test_get_missing_returns_default(self):
        cache = LRUCache(max_size=2)
        assert cache.get("missing") is None
        assert cache.get("missing", 42) == 42

    def test_overwrite_value(self):
        cache = LRUCache(max_size=2)
        cache.put("k", "old")
        cache.put("k", "new")
        assert cache.get("k") == "new"


class TestEvictionOrder:
    def test_evicts_least_recently_used(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # evicts "a"
        assert "a" not in cache
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_get_refreshes_recency(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.get("a") == 1  # refresh "a"
        cache.put("c", 3)  # now evicts "b"
        assert "b" not in cache
        assert cache.get("a") == 1
        assert cache.get("c") == 3

    def test_put_existing_key_refreshes_recency(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)  # update refreshes "a"
        cache.put("c", 3)  # evicts "b"
        assert "b" not in cache
        assert cache.get("a") == 10
        assert cache.get("c") == 3


class TestEdgeCases:
    def test_max_size_one(self):
        cache = LRUCache(max_size=1)
        cache.put("a", 1)
        assert len(cache) == 1
        cache.put("b", 2)
        assert "a" not in cache
        assert cache.get("b") == 2
        assert len(cache) == 1

    @pytest.mark.parametrize("bad", [0, -1, -100, 1.5, "3", None, True])
    def test_invalid_max_size_raises(self, bad):
        with pytest.raises(ValueError):
            LRUCache(max_size=bad)


class TestDunderAndClear:
    def test_len_and_contains(self):
        cache = LRUCache(max_size=3)
        assert len(cache) == 0
        assert "x" not in cache
        cache.put("x", 1)
        cache.put("y", 2)
        assert len(cache) == 2
        assert "x" in cache
        assert "y" in cache
        assert "z" not in cache

    def test_clear(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert len(cache) == 0
        assert "a" not in cache
        assert "b" not in cache
        # Cache remains usable after clear.
        cache.put("c", 3)
        assert cache.get("c") == 3


class TestConcurrency:
    def test_concurrent_access_is_safe(self):
        cache = LRUCache(max_size=64)
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(500):
                    key = f"k{(worker_id * 7 + i) % 128}"
                    cache.put(key, i)
                    cache.get(key)
                    cache.get(f"missing-{i}")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(cache) <= 64
