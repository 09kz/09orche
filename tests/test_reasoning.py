import pytest

from orche.reasoning import build_reasoning_param


def test_none_returns_none():
    assert build_reasoning_param(None) is None


@pytest.mark.parametrize(
    "effort", ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
)
def test_valid_efforts(effort):
    assert build_reasoning_param(effort) == {"effort": effort}


def test_invalid_effort_raises():
    with pytest.raises(ValueError, match="reasoning_effort must be one of"):
        build_reasoning_param("ultra-mega-high")
