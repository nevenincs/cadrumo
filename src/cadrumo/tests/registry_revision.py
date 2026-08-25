"""Law-determined registry revision resolution for tests.

A test fixture needing the revision id for a ``(modelo, filing_year, period)``
filing target must resolve it the same way production does -- never pin a
literal, which goes stale the moment AEAT publishes a new design (as happened
when the former M303 post-2022 selector was capped at 2025 and every 2026
target silently moved to ``2026-y-siguientes``).
"""

from __future__ import annotations

from ..application.modelo.work_addressing import resolve_registry_revision_for_work_target
from ..core import Period


def active_registry_revision_id(*, modelo: str, filing_year: int, period: str) -> str:
    """Return the law-determined registry revision for a filing target.

    AEAT binds every ``(modelo, filing_year, period)`` triple to exactly one
    revision by publishing orden, so "which revision applies" is a derived
    fact and never an input. Resolving it here keeps fixtures on the same
    authority the production paths use.
    """
    return resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        registry_revision_id=None,
    )
