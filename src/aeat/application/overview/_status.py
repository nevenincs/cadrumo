"""Filing-status taxonomy for the ``aeat app live filed`` surface.

This module owns the single authoritative definition of ``FilingStatus``.
It is the sole source for the ``"filed"`` string token used in:

- the Typer sub-app name for ``aeat app live filed``
- the operator-surface contract command tuple for the ``LIVE`` family
"""

from __future__ import annotations

from enum import StrEnum


class FilingStatus(StrEnum):
    """Single-member status enum for the ``filed`` CLI surface.

    Attributes:
        FILED: The operator has performed an active live-capture against
            the AEAT filed-declarations register.  The string value
            ``"filed"`` is used as the Typer sub-app name and as the
            operator-surface contract command token.
    """

    FILED = "filed"
