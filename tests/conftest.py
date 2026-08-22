import pytest

from conclave import _http, cost


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(_http, "BASE_DELAY", 0.001)


@pytest.fixture(autouse=True)
def reset_cost_tracker():
    cost._spent_usd = 0.0
    yield
    cost._spent_usd = 0.0
