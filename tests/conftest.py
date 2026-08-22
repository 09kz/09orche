import pytest

from conclave import client


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(client, "BASE_DELAY", 0.001)
