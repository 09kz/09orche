"""Support for OpenRouter's unified `reasoning` request parameter.

Idea borrowed from Wally-Ahmed's openrouter-subagents
(https://github.com/Wally-Ahmed/openrouter-subagents), which exposes the same
knob under a friendlier name than raw model/vendor reasoning params. Credit
where due — thanks, Wally.
"""

VALID_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def build_reasoning_param(effort: str | None) -> dict | None:
    """Translate a friendly effort level into OpenRouter's `reasoning` object.

    Raises ValueError on an unrecognized effort level.
    """
    if effort is None:
        return None
    if effort not in VALID_EFFORTS:
        raise ValueError(f"reasoning_effort must be one of {VALID_EFFORTS} (got {effort!r})")
    return {"effort": effort}
