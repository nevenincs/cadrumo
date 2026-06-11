"""Registry lookup for filing window close dates (plazo voluntario).

Provides a profile-free function to ask "when does the plazo voluntario
close for this modelo + filing year + period?" directly from the registry
deadline windows.  The result feeds the extemporaneidad detection surface
in :func:`aeat.entrypoints.cli._modelo._work_unit_plazo_lines` and in the
anti-tautology test suite.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from ...core import Period


def resolve_filing_closes_on(modelo: str, filing_year: int, period: str) -> date | None:
    """Return the close date of the plazo voluntario for a modelo+year+period.

    Queries the validated registry authority for ``filing_year`` and
    returns the ``closes_on`` of the first matching
    :class:`~aeat.domain.calculations.registry.DeadlineWindowDefinition`.

    Matching rule: the registry window period must carry the same
    filing year and bare registry period token as the supplied WorkUnit
    period (e.g. ``"1T"``, ``"0A"``, ``"01"``).

    Returns ``None`` when the registry carries no window for the
    combination — either the modelo has no deadline windows registered
    for that year, or the period token does not match any window.
    ``None`` is a benign data-gap signal; callers should degrade
    gracefully rather than treating it as fatal.

    Args:
        modelo: AEAT modelo code (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the work unit was created.
        period: WorkUnit bare registry period token (e.g. ``"1T"``, ``"0A"``, ``"01"``).

    Returns:
        The :class:`~datetime.date` on which the filing window closes,
        or ``None`` if not found.
    """
    return _resolve_closes_on_cached(modelo, filing_year, period)


@lru_cache(maxsize=256)
def _resolve_closes_on_cached(modelo: str, filing_year: int, period: str) -> date | None:
    from ...core.resources import resources
    from ..calculations.registry import RegistryError

    authority = resources().modelos.authority
    registry_period = _normalise_work_unit_period_token(period)

    # Annual-period modelos (e.g. M100) are registered under the calendar year
    # in which the return is actually filed (filing_year + 1 in the TOML), while
    # the WorkUnit carries the tax year (filing_year).  Try both years so the
    # resolver handles both quarterly/monthly windows (tax year == registry year)
    # and annual windows (registry year == tax year + 1).
    for query_year in (filing_year, filing_year + 1):
        try:
            windows = authority.deadline_windows(query_year)
        except RegistryError:
            continue
        for window_modelo, _revision, window in windows:
            if window_modelo != modelo:
                continue
            # window.period is now a typed Period; match on filing_year + registry_token.
            # Annual windows may be registered under filing_year + 1 (tax year
            # == filing_year, registry year == filing_year + 1 for annual modelos).
            wp = window.period
            year_matches = wp.filing_year == filing_year or (
                wp.registry_token == "0A" and wp.filing_year == filing_year + 1
            )
            if year_matches and wp.registry_token == registry_period:
                return window.closes_on
    return None


def _normalise_work_unit_period_token(period: str) -> str:
    try:
        return Period.from_year_and_code(2000, period).registry_token
    except ValueError:
        return ""


__all__ = ["resolve_filing_closes_on"]
