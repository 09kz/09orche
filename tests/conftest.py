import pytest

from conclave import _http


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(_http, "BASE_DELAY", 0.001)
