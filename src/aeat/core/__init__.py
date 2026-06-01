"""Core cross-cutting package namespace."""

from __future__ import annotations

from ._models import STRICT_FROZEN_CONFIG
from ._period import StandardPeriodCode

__all__: list[str] = [
    "AggregationSourceKind",
    "StandardPeriodCode",
    "STRICT_FROZEN_CONFIG",
]


def __getattr__(name: str) -> object:
    if name == "AggregationSourceKind":
        from .aggregation import AggregationSourceKind

        return AggregationSourceKind
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
