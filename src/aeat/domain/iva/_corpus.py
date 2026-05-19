"""VAT catalogue access through committed registry data."""

from __future__ import annotations

from datetime import date

from ...core.config import Settings
from ._catalogue import resolve_catalogue
from ._schema import IvaCatalogue


def load_iva_rules_from_manual(
    year: int,
    *,
    settings: Settings | None = None,
) -> IvaCatalogue:
    """Load the reviewed VAT catalogue for ``year``."""

    del settings
    return resolve_catalogue(on=date(year, 1, 1))


__all__ = ["load_iva_rules_from_manual"]
