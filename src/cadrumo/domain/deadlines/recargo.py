"""Loader and resolver for the Ley 58/2003 art-27 recargo bracket table.

The bracket schedule is published in the typed runtime authority so surcharge
percentages stay outside Python source and can be revised without touching
engine code. Two functions are exposed:

- :func:`load_recargo_bands` adapts the published projection into a tuple
  of :class:`domain.deadlines.RecargoBand` records.
- :func:`completed_months_late` counts the COMPLETED months between the
  filing deadline and the presentation date (Art. 27.2 LGT counts only
  whole months; a fractional month does not count).
- :func:`resolve_recargo_band` selects the graduated band whose
  ``[min_completed_months, max_completed_months]`` window contains a given
  completed-months value.
- :func:`more_than_twelve_months_elapsed` decides the 15% + intereses tail:
  it fires only STRICTLY AFTER the twelve-month anniversary of the deadline
  (the anniversary day itself stays in the graduated band per Art. 27.2), a
  boundary a completed-months count alone cannot resolve.

The deadline engine calls :func:`build_recovery_for_overdue` to
populate the :class:`Recovery` field on every OVERDUE
:class:`ModeloDeadline`.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import date

from ...core.period import Period
from .errors import DeadlineValidationError
from .models import RecargoBand, Recovery


def load_recargo_bands() -> tuple[RecargoBand, ...]:
    """Adapt the recargo brackets from the bundled published authority.

    Returns:
        Tuple of :class:`RecargoBand` records ordered by
        ``min_completed_months`` ascending.

    """
    from ..calculations.registry.authority import bundled_authority

    return tuple(
        RecargoBand.model_validate(
            {
                "id": published.id,
                "min_completed_months": published.min_completed_months,
                "max_completed_months": published.max_completed_months,
                "surcharge_pct": published.surcharge_pct,
                "interest_applies": published.interest_applies,
                "legal_ref": published.legal_ref,
            }
        )
        for published in sorted(
            bundled_authority().catalogues.runtime.recargo_bands.values(),
            key=lambda band: band.min_completed_months,
        )
    )


def completed_months_late(closes_on: date, reference_today: date) -> int:
    """Return the number of COMPLETED months between deadline and presentation.

    Art. 27.2 LGT escalates the recargo "por cada mes completo de retraso" —
    by each *completed* month of delay. A month is completed only when the
    presentation date has reached the same day-of-month as the deadline in a
    later month; a fractional (incomplete) month does not count.

    Args:
        closes_on: The filing window's close date (deadline).
        reference_today: The date the self-assessment is presented.

    Returns:
        Completed months of delay, ``>= 0`` (``0`` when filed late but within
        the first incomplete month).
    """
    if reference_today <= closes_on:
        return 0
    months = (reference_today.year - closes_on.year) * 12 + (reference_today.month - closes_on.month)
    if reference_today.day < closes_on.day:
        months -= 1
    return max(0, months)


def twelve_month_anniversary(closes_on: date) -> date:
    """Return the twelve-month anniversary of the filing window close date.

    Art. 27.2 LGT ties the 15% + intereses tail to the filing being presented
    "una vez transcurridos 12 meses" — once the twelve-month period has fully
    elapsed. This helper returns the ``término`` of that period: the same
    day-of-month twelve months later. A day-of-month that does not exist in the
    target month (a 29 February close carried to a non-leap year) clamps to the
    month's last day, matching the AEAT "mismo día del mes" convention.

    Args:
        closes_on: The filing window's close date (deadline).

    Returns:
        The date on which twelve months have elapsed since ``closes_on``.
    """
    target_year = closes_on.year + 1
    target_month = closes_on.month
    last_day = calendar.monthrange(target_year, target_month)[1]
    return date(target_year, target_month, min(closes_on.day, last_day))


def more_than_twelve_months_elapsed(closes_on: date, reference_today: date) -> bool:
    """Return whether ``reference_today`` is STRICTLY past the twelve-month term.

    Art. 27.2 LGT: the 15% + intereses de demora tail applies only when the
    self-assessment is presented "una vez transcurridos 12 meses" — after the
    twelve-month period has elapsed. The statute pins the boundary via the
    interest clause: intereses run "desde el día siguiente al término de los 12
    meses". The anniversary date itself (the ``término``) therefore still belongs
    to the graduated 1%-per-completed-month band; only the day after and beyond
    fall into the 15% tail.

    Args:
        closes_on: The filing window's close date (deadline).
        reference_today: The date the self-assessment is presented.

    Returns:
        ``True`` when ``reference_today`` is strictly after the twelve-month
        anniversary of ``closes_on`` (the 15% + interest tail applies); ``False``
        on or before the anniversary (the graduated band applies).
    """
    return reference_today > twelve_month_anniversary(closes_on)


def _interest_bearing_tail_band(bands: Sequence[RecargoBand]) -> RecargoBand:
    """Return the single 15% + intereses de demora tail band (Art. 27.2 LGT).

    The tail is selected by its ``interest_applies`` marker rather than by a
    completed-months window, because the day immediately after the twelve-month
    anniversary still reports only twelve completed months yet already carries the
    15% consequence — a completed-months lookup cannot distinguish it from the
    anniversary (see :func:`more_than_twelve_months_elapsed`).

    Raises:
        DeadlineValidationError: When the band table does not carry exactly one
            interest-bearing tail band (a registry-shape error).
    """
    tail = [band for band in bands if band.interest_applies]
    if len(tail) != 1:
        raise DeadlineValidationError(
            f"recargo band table must carry exactly one interest-bearing tail band; got {len(tail)}",
        )
    return tail[0]


def resolve_recargo_band(completed_months: int, bands: Sequence[RecargoBand]) -> RecargoBand:
    """Return the band whose window contains ``completed_months``.

    Args:
        completed_months: Completed months past the filing window's close
            date, as returned by :func:`completed_months_late`. Must be
            ``>= 0``.
        bands: Tuple of bands as returned by :func:`load_recargo_bands`.

    Returns:
        The matching :class:`RecargoBand`.

    Raises:
        DeadlineValidationError: When ``completed_months < 0`` or no band's
            window covers the value (which would indicate an authority gap).
    """
    if completed_months < 0:
        raise DeadlineValidationError(
            f"resolve_recargo_band: completed_months must be >= 0; got {completed_months}",
        )
    for band in bands:
        upper = band.max_completed_months if band.max_completed_months is not None else completed_months
        if band.min_completed_months <= completed_months <= upper:
            return band
    raise DeadlineValidationError(f"resolve_recargo_band: no band covers completed_months={completed_months}")


def build_recovery_for_overdue(
    *,
    closes_on: date,
    reference_today: date,
    modelo: str,
    period: Period,
    bands: Sequence[RecargoBand] | None = None,
) -> Recovery:
    """Resolve the :class:`Recovery` payload for an OVERDUE obligation.

    The recargo percentage is computed precisely per Art. 27.2 LGT: 1% + 1% per
    COMPLETED month of delay while inside the first twelve months (up to 13% at
    the twelve-month anniversary), and 15% + intereses de demora only once the
    filing is presented "una vez transcurridos 12 meses" — STRICTLY AFTER the
    twelve-month anniversary. The tail boundary is date-gated rather than derived
    from the completed-months count alone: the day immediately after the
    anniversary still reports twelve completed months yet already carries the 15%
    consequence, so :func:`more_than_twelve_months_elapsed` decides the tail while
    :func:`resolve_recargo_band` resolves the graduated band otherwise.

    Args:
        closes_on: The filing window's close date (deadline).
        reference_today: The date the self-assessment is presented.
        modelo: Modelo identifier for the overdue obligation.
        period: Typed filing period for the overdue obligation.
        bands: Optional pre-loaded band table; when ``None``, the published
            runtime authority is adapted.

    Returns:
        A :class:`Recovery` carrying the resolved band and legal reference.
    """
    band_table = bands if bands is not None else load_recargo_bands()
    if more_than_twelve_months_elapsed(closes_on, reference_today):
        resolved = _interest_bearing_tail_band(band_table)
    else:
        months = completed_months_late(closes_on, reference_today)
        resolved = resolve_recargo_band(months, band_table)
    return Recovery(
        still_filable=True,
        recargo_band=resolved,
    )


__all__ = [
    "build_recovery_for_overdue",
    "completed_months_late",
    "load_recargo_bands",
    "more_than_twelve_months_elapsed",
    "resolve_recargo_band",
    "twelve_month_anniversary",
]
