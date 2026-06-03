"""Core cross-cutting infrastructure shared by every ``aeat`` layer.

The core layer holds the typed primitives, configuration, and boundary
utilities that the domain, application, adapter, and entrypoint layers all
build on, while depending on none of them — the innermost ring of the
hexagonal architecture.

Direct exports:

* :data:`STRICT_FROZEN_CONFIG` — the frozen-strict pydantic ``ConfigDict``
  shared by immutable boundary models.
* :class:`StandardPeriodCode` — the closed set of AEAT filing-period tokens.
* :class:`AggregationSourceKind` — provenance kinds for aggregated ledger
  values, resolved lazily to avoid an import cycle.

Major subpackages: :mod:`aeat.core.config` (the central settings surface),
:mod:`aeat.core.errors` (the error taxonomy and registry),
:mod:`aeat.core.money` and :mod:`aeat.core.decimal` (Decimal primitives),
:mod:`aeat.core.time` (clock helpers), :mod:`aeat.core.identity`
(NIF / NIE parsing), :mod:`aeat.core.access_gate` (live-read and
write-refusal gating), :mod:`aeat.core.redaction` (output redaction),
:mod:`aeat.core.classification` (sensitivity policy), and
:mod:`aeat.core.observability` (run-trace logging).
"""

from __future__ import annotations

from ._models import STRICT_FROZEN_CONFIG
from ._period import StandardPeriodCode

__all__: list[str] = [
    "STRICT_FROZEN_CONFIG",
    "AggregationSourceKind",
    "StandardPeriodCode",
]


def __getattr__(name: str) -> object:
    if name == "AggregationSourceKind":
        from .aggregation import AggregationSourceKind

        return AggregationSourceKind
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
