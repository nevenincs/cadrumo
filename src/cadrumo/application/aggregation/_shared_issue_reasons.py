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
tooling, locale lookup, and downstream reporting can group them under
one key. The two enums survive natively in their respective
modules; this file is the single source of truth for the shared
strings.

The annual Modelo 100 expense pipeline and the Modelo 130 gasto pipeline both
evaluate a row through its category's proportionality rule, so the five
refusals that evaluation can raise are spelled once here as well.
"""

from __future__ import annotations

from typing import Final

UNSUPPORTED_DIRECTION: Final[str] = "unsupported_direction"
UNSUPPORTED_CURRENCY: Final[str] = "unsupported_currency"
UNCLASSIFIED_BUSINESS_STATE: Final[str] = "unclassified_business_state"
PERSONAL_TRANSACTION: Final[str] = "personal_transaction"
OUTSIDE_PERIOD: Final[str] = "outside_period"
UNKNOWN_CATEGORY: Final[str] = "unknown_category"
MISSING_CATEGORY_PROFILE: Final[str] = "missing_category_profile"
REGION_UNDECLARED_FOR_OVERRIDE: Final[str] = "region_undeclared_for_override"
INVALID_LEDGER_FACT: Final[str] = "invalid_ledger_fact"
INELIGIBLE_DEDUCTIBILITY: Final[str] = "ineligible_deductibility"


__all__ = [
    "INELIGIBLE_DEDUCTIBILITY",
    "INVALID_LEDGER_FACT",
    "MISSING_CATEGORY_PROFILE",
    "OUTSIDE_PERIOD",
    "PERSONAL_TRANSACTION",
    "REGION_UNDECLARED_FOR_OVERRIDE",
    "UNCLASSIFIED_BUSINESS_STATE",
    "UNKNOWN_CATEGORY",
    "UNSUPPORTED_CURRENCY",
    "UNSUPPORTED_DIRECTION",
]
