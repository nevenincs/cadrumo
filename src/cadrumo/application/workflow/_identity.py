"""Stable identity helpers shared by workflow state and run contracts."""

from ...core import Period


def period_identity_segment(period: Period) -> str:
    """Return the stable non-combined identity segment for ``period``."""
    return f"{period.filing_year}:{period.registry_token}"
