"""Stable identity helpers shared by workflow state and run contracts."""

from ...core.period import Period


def period_identity_segment(period: Period) -> str:
    """Return the stable non-combined identity segment for ``period``.

    Raises:
        TypeError: ``period`` is not a typed :class:`~cadrumo.core.Period`. A
            combined token such as ``"2026Q1"`` fuses the filing year and the
            registry code into one opaque string, and admitting it here would
            mint a run or state id that nothing can decompose back into the two
            values the identity claims to carry.
    """
    if not isinstance(period, Period):
        raise TypeError(
            f"period identity requires a typed cadrumo.core.Period, not {type(period).__name__}"
        )
    return f"{period.filing_year}:{period.registry_token}"
