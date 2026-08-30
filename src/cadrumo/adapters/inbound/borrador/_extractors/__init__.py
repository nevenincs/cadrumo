"""Per-año Modelo 100 observed-value extractor registry.

Registers the concrete extractor classes (one per tax year) and exposes
:func:`get_extractor` for the public
:func:`adapters.inbound.borrador.parse_borrador` entry point.

The observed-value extraction logic is year-agnostic across the currently
registered 2021-2025 extractor years: AEAT Renta Web Open borrador PDFs print
casilla rows with the same ``NNNN label amount`` format. A single concrete class
covers those supported years; per-year entries in the registry signal which
years are in scope without requiring distinct class implementations for each.

This registry is an adapter dispatch table, not a registry-authority lookup.
Callers that need target-casilla coverage still provide a
:class:`adapters.inbound.borrador.BorradorExtractionProfile` to
the public parser.

See Also:
    :class:`adapters.inbound.borrador._extractors.modelo_100_summary_v2025.Modelo100ObservedV2025Extractor`
        Current year-stable implementation used by every registered year.
    :class:`adapters.inbound.borrador.BorradorParseMode`
        Caller-selected observed versus registry-profile validation mode.
"""

from __future__ import annotations

from ..errors import BorradorParseError as _BorradorParseError
from .modelo_100_summary_v2025 import Modelo100ObservedV2025Extractor as _Modelo100ObservedV2025Extractor

# The generic observed-value extraction algorithm is year-stable across the
# supported 2021-2025 extractor registrations: the observed casilla-row grammar
# is unchanged in the covered parser evidence.
# Separate entries allow callers to pass año_override=2021..2025 without
# BorradorParseError while reusing the same implementation.
_REGISTRY_BY_AÑO: dict[int, type[_Modelo100ObservedV2025Extractor]] = {
    2021: _Modelo100ObservedV2025Extractor,
    2022: _Modelo100ObservedV2025Extractor,
    2023: _Modelo100ObservedV2025Extractor,
    2024: _Modelo100ObservedV2025Extractor,
    2025: _Modelo100ObservedV2025Extractor,
}


def get_extractor(año: int) -> _Modelo100ObservedV2025Extractor:
    """Return a fresh Modelo 100 observed-value extractor for the given tax year.

    Args:
        año: The four-digit tax year for which an extractor is required.

    Returns:
        A freshly instantiated extractor registered for the requested ``año``.

    Raises:
        _BorradorParseError: When no extractor is registered for ``año``.
    """
    cls = _REGISTRY_BY_AÑO.get(año)
    if cls is None:
        known = sorted(_REGISTRY_BY_AÑO.keys())
        raise _BorradorParseError(f"no Modelo 100 observed-value extractor for año={año}; supported: {known}")
    return cls()


__all__ = ["get_extractor"]
