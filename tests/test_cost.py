import pytest

from conclave import cost


def test_no_budget_by_default():
    assert cost.limit_usd() is None
    cost.check_budget("acme/foo")  # should not raise


def test_budget_from_env(monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "5.00")
    assert cost.limit_usd() == 5.00


def test_invalid_budget_env_treated_as_unset(monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "not-a-number")
    assert cost.limit_usd() is None


def test_record_accumulates():
    cost.record(0.01)
    cost.record(0.02)
    assert cost.spent_usd() == pytest.approx(0.03)


def test_record_ignores_none_and_zero():
    cost.record(None)
    cost.record(0)
    assert cost.spent_usd() == 0.0


def test_check_budget_raises_once_spent_reaches_limit(monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "0.05")
    cost.record(0.05)
    with pytest.raises(cost.BudgetExceededError, match="acme/foo"):
        cost.check_budget("acme/foo")


def test_check_budget_allows_spend_under_limit(monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "1.00")
    cost.record(0.10)
    cost.check_budget("acme/foo")  # should not raise


def test_status_without_budget():
    text = cost.status()
    assert "no CONCLAVE_MAX_COST_USD" in text


def test_status_with_budget(monkeypatch):
    monkeypatch.setenv("CONCLAVE_MAX_COST_USD", "2.50")
    cost.record(0.25)
    text = cost.status()
    assert "$0.2500" in text
    assert "$2.50" in text
