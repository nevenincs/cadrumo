"""IVA catalogue access through committed registry data.

:func:`load_iva_rules_from_manual` preserves the manual-loader entry point
while delegating to :func:`resolve_catalogue` and returning the reviewed
:class:`IvaCatalogue` for the requested filing year.
"""

from __future__ import annotations

from datetime import date

from ...core.config import Settings
from .catalogue import resolve_catalogue
from .schema import IvaCatalogue


def load_iva_rules_from_manual(
    year: int,
    *,
    settings: Settings | None = None,
) -> IvaCatalogue:
    """Load the reviewed :class:`IvaCatalogue` for ``year``."""
    del settings
    return resolve_catalogue(on=date(year, 1, 1))


__all__ = ["load_iva_rules_from_manual"]
