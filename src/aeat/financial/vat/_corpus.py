"""Corpus loader for the VAT substrate.

The loader is intentionally minimal: for 2025 it falls back to the
hand-coded :data:`VAT_CATALOGUE_2025` when the Manual práctico IVA
corpus has no extracted, year-keyed JSON catalogue on disk. The
fallback is logged at INFO so operators notice the miss.

For any year != 2025 the loader raises
:class:`VatCatalogueError`. When the on-disk extraction pipeline
lands it will drop a ``{year}.json`` file under
``AEAT_VAT_CATALOGUE_ROOT`` and this function can grow a proper
pydantic-driven loader without changing its signature.
"""

from __future__ import annotations

from aeat.config import Settings
from aeat.logging import get_logger

from ._catalogue import VAT_CATALOGUE_2025
from ._schema import VATCatalogue
from .errors import VatCatalogueError

_logger = get_logger(__name__)

_SUPPORTED_FALLBACK_YEARS: frozenset[int] = frozenset({2025})


def load_vat_rules_from_manual(
    year: int,
    *,
    settings: Settings | None = None,
) -> VATCatalogue:
    """Load a VAT catalogue for ``year``.

    The implementation currently returns the in-memory 2025
    catalogue when ``year == 2025`` and raises
    :class:`VatCatalogueError` otherwise. A future extraction
    pipeline will grow this function into a disk-first loader that
    reads ``{settings.aeat_vat_catalogue_root}/{year}.json``.

    Args:
        year: Tax year for which a catalogue is requested.
        settings: Optional :class:`aeat.config.Settings` instance
            carrying the catalogue root override. Unused until the
            disk-backed loader lands but kept in the signature so
            downstream callers can start wiring it immediately.

    Returns:
        A :class:`VATCatalogue` for the requested year.

    Raises:
        VatCatalogueError: If ``year`` is not one of the currently
            supported fallback years.
    """
    del settings  # Placeholder until the disk-backed loader lands.
    if year not in _SUPPORTED_FALLBACK_YEARS:
        raise VatCatalogueError(
            f"no VAT catalogue available for year={year}; supported fallback years: {sorted(_SUPPORTED_FALLBACK_YEARS)}"
        )
    _logger.info(
        "load_vat_rules_from_manual: falling back to in-memory VAT_CATALOGUE_2025 for year=%d",
        year,
    )
    return VAT_CATALOGUE_2025


__all__ = ["load_vat_rules_from_manual"]
