"""Cross-modelo reconciliation primitives for the :mod:`aeat.domain.filing` domain.

Hosts the helpers that compare aggregated periodic filings against their
annual summaries, surfacing arithmetic and identity drift before submission.
"""

from ._errors import (
    DeclaracionParseError,
    ReconciliationDriftError,
    ReconciliationError,
)

__all__ = [
    "DeclaracionParseError",
    "ReconciliationDriftError",
    "ReconciliationError",
]
