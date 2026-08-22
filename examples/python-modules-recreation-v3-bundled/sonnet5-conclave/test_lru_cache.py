import threading

from lru_cache import LRUCache


def test_basic_get_put():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("missing") is None


def test_overwrite_value():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("a", 99)
    assert c.get("a") == 99


def test_eviction_order():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1  # "a" now most recently used
    c.put("c", 3)           # evicts "b"
    assert "b" not in c
    assert c.get("a") == 1
    assert c.get("c") == 3


def test_put_counts_as_use():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)  # refreshes "a"
    c.put("c", 3)   # evicts "b"
    assert "b" not in c
    assert c.get("a") == 10


def test_capacity_respected():
    c = LRUCache(5)
    for i in range(20):
        c.put(i, i * 2)
    assert len(c) == 5
    for i in range(15, 20):
        assert c.get(i) == i * 2


def test_invalid_capacity():
    import pytest
    with pytest.raises(ValueError):
        LRUCache(0)


def test_concurrency_stress():
    c = LRUCache(100)
    errors = []

    def worker(tid):
        try:
            for i in range(2000):
                key = (tid * 7 + i) % 150
                c.put(key, tid)
                v = c.get(key)
                assert v is None or isinstance(v, int)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(c) <= 100
