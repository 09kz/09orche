"""Best-effort, process-lifetime spend guardrail for paid OpenRouter models.

Tracks cumulative `usage.cost` (as reported by OpenRouter on every response)
across all calls made by this server process. Resets when the process
restarts — this caps a single runaway session, not spend across restarts,
and isn't atomic against concurrent calls racing past the limit together.
For a hard, persistent budget, use OpenRouter's own account-level spend
controls instead.
"""

import os

_spent_usd = 0.0


class BudgetExceededError(Exception):
    pass


def limit_usd() -> float | None:
    """The configured budget, or None if ORCHE_MAX_COST_USD isn't set.

    Assumes the value was already validated at startup (see
    `orche.server.build_server`) — falls back to None on a bad value
    rather than crashing an in-flight tool call.
    """
    raw = os.environ.get("ORCHE_MAX_COST_USD")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def check_budget(model_id: str) -> None:
    """Raise BudgetExceededError if the session has already hit its budget."""
    limit = limit_usd()
    if limit is not None and _spent_usd >= limit:
        raise BudgetExceededError(
            f"refusing to call {model_id}: this session has spent "
            f"${_spent_usd:.4f} of its ${limit:.2f} ORCHE_MAX_COST_USD budget"
        )


def record(cost: float | None) -> None:
    global _spent_usd
    if cost:
        _spent_usd += cost


def spent_usd() -> float:
    return _spent_usd


def status() -> str:
    limit = limit_usd()
    if limit is None:
        return f"Spend this session: ${_spent_usd:.4f} (no ORCHE_MAX_COST_USD budget set)"
    return f"Spend this session: ${_spent_usd:.4f} of ${limit:.2f} budget"
