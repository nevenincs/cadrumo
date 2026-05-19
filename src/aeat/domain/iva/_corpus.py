"""VAT catalogue access through committed registry data."""

from __future__ import annotations

from datetime import date

from ...core.config import Settings
from ._catalogue import resolve_catalogue
from ._schema import VATCatalogue


def load_vat_rules_from_manual(
    year: int,
    *,
    settings: Settings | None = None,
) -> VATCatalogue:
    """Load the reviewed VAT catalogue for ``year``."""

    del settings
    return resolve_catalogue(on=date(year, 1, 1))


__all__ = ["load_vat_rules_from_manual"]
