"""Shared issue-reason strings for ledger aggregators.

Several aggregator pipelines (IVA, Modelo 100 Renta expense, M130 income, and
M130 gasto) emit traceable rejection issues for rows the upstream catalogue
could not classify. The reason vocabularies still diverge by domain, but five
upstream filter rejections converge:

- A direction the ledger cannot project.
- A currency outside the EUR-only scope.
- A row whose ``business_classification`` lifecycle state is
  unclassified.
- A row flagged ``PERSONAL`` rather than business.
- A row whose date falls outside the requested period.

Both ledgers spell those five rejections identically so cross-ledger
tooling, locale lookup, and downstream telemetry can group them under
one key. The two enums survive natively in their respective
modules; this file is the single source of truth for the shared
strings.
"""

from __future__ import annotations

from typing import Final

UNSUPPORTED_DIRECTION: Final[str] = "unsupported_direction"
UNSUPPORTED_CURRENCY: Final[str] = "unsupported_currency"
UNCLASSIFIED_BUSINESS_STATE: Final[str] = "unclassified_business_state"
PERSONAL_TRANSACTION: Final[str] = "personal_transaction"
OUTSIDE_PERIOD: Final[str] = "outside_period"


__all__ = [
    "OUTSIDE_PERIOD",
    "PERSONAL_TRANSACTION",
    "UNCLASSIFIED_BUSINESS_STATE",
    "UNSUPPORTED_CURRENCY",
    "UNSUPPORTED_DIRECTION",
]
