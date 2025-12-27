"""Small math helpers."""

def clamp(value: float, min_value: float, max_value: float) -> float:
    """Return *value* limited to the inclusive range [min_value, max_value]."""
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value
