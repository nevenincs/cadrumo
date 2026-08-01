"""Registry lookup for filing window close dates (plazo voluntario).

Provides a profile-free function to ask "when does the plazo voluntario
close for this modelo + filing year + period?" directly from the registry
deadline windows.  The result feeds the extemporaneidad detection surface
in :func:`cadrumo.entrypoints.cli._modelo._work_unit_plazo_lines` and in the
anti-tautology test suite.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING

from ...core import Period

if TYPE_CHECKING:
    from ..calculations.registry import DeadlineWindowDefinition


def resolve_filing_closes_on(modelo: str, filing_year: int, period: Period) -> date | None:
    """Return the close date of the plazo voluntario for a modelo+year+period.

    Queries the validated registry authority for ``filing_year`` and
    returns the ``closes_on`` of the first matching
    :class:`~cadrumo.domain.calculations.registry.DeadlineWindowDefinition`.

    Matching rule: the registry window period must carry the same
    filing year and bare registry period token as the supplied ``WorkUnit``
    period (e.g. ``"1T"``, ``"0A"``, ``"01"``).

    Annual Modelo 100 uses its tax year as the registry key even though
    its normal campaign runs in the following calendar year. A close date
    for tax year 2024 can therefore fall in 2025. This function never
    borrows a following-year or future-year window when an exact match is
    absent.

    Returns ``None`` when no registry window exactly matches the
    combination. The modelo might have no deadline window for that year,
    or its period token might not match any window. ``None`` means the
    deadline data is unavailable; callers continue without a close date.

    Args:
        modelo: Agencia Estatal de Administración Tributaria (AEAT) modelo code
            (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the work unit was created.
        period: ``WorkUnit`` bare registry period token (e.g. ``"1T"``,
            ``"0A"``, ``"01"``).

    Returns:
        The :class:`~datetime.date` on which the filing window closes,
        or ``None`` if not found.
    """
    window = resolve_filing_window(modelo, filing_year, period)
    return None if window is None else window.closes_on


@lru_cache(maxsize=256)
def resolve_filing_window(modelo: str, filing_year: int, period: Period) -> DeadlineWindowDefinition | None:
    """Return the registry deadline window for a modelo+year+period, or ``None``.

    This is the single matching authority for "which registry deadline window
    covers this filing target". Every consumer — the extemporaneidad surface
    that needs only :attr:`closes_on`, and the overview calendar that also
    needs ``opens_on`` and ``payment_cutoff_on`` — resolves through here, so a
    change to the year/token matching rule or to the no-window behaviour can
    never move one surface without the other.

    Matching rule: the registry window's period must carry the same filing year
    and the same bare registry period token as the requested ``period`` (e.g.
    ``"1T"``, ``"0A"``, ``"01"``). No following-year or future-year window is
    ever borrowed when an exact match is absent.

    Args:
        modelo: Agencia Estatal de Administración Tributaria (AEAT) modelo code
            (e.g. ``"130"``, ``"303"``).
        filing_year: Tax year for which the filing target was created.
        period: The typed filing period to match.

    Returns:
        The matching
        :class:`~cadrumo.domain.calculations.registry.DeadlineWindowDefinition`,
        or ``None`` when the registry declares no window for the combination.
    """
    from ...core.resources import resources
    from ..calculations.registry import RegistryError

    authority = resources().modelos.authority

    try:
        windows = authority.deadline_windows(filing_year)
    except RegistryError:
        return None
    for window_modelo, _revision, window in windows:
        if window_modelo != modelo:
            continue
        wp = window.period
        if wp.filing_year == filing_year and wp.registry_token == period.registry_token:
            return window
    return None


__all__ = ["resolve_filing_closes_on", "resolve_filing_window"]
