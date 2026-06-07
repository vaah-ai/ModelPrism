"""Helper utilities for metric processing.

Functions here are intentionally kept free of framework dependencies
(FastAPI, SQLAlchemy) so they can be imported by tests without
loading the full application stack.
"""

from __future__ import annotations

from typing import Any


def avg_gpu_field(gpus: list[dict[str, Any]], field: str) -> float | None:
    """Compute the average of a numeric field across all GPU entries.

    Returns ``None`` if the field is not present on any GPU.
    """
    values: list[float] = []
    for g in gpus:
        val = g.get(field)
        if val is not None:
            values.append(float(val))
    if not values:
        return None
    return sum(values) / len(values)
