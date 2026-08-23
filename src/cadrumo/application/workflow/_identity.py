"""Stable identity helpers shared by workflow state and run contracts."""

from ...core import Period


def period_identity_segment(period: Period) -> str:
    """Return the stable non-combined identity segment for ``period``."""
    if not isinstance(period, Period):
        raise TypeError(f"period must be a cadrumo.core.Period instance, got {type(period).__name__}")
    return f"{period.filing_year}:{period.registry_token}"
