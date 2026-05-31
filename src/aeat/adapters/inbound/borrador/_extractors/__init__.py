"""Per-año Modelo 100 observed-value extractor registry.

Registers the concrete extractor classes (one per tax year) and exposes
:func:`get_extractor` for the public
:func:`aeat.adapters.inbound.borrador.parse_borrador` entry point.

The observed-value extraction logic is year-agnostic: the AEAT Renta Web Open
borrador prints casilla rows with the same ``NNNN label amount`` format across
all years from 2021 onward.  A single concrete class covers all supported
years; per-year entries in the registry signal which years are in scope without
requiring distinct class implementations for each.
"""

from __future__ import annotations

from .._errors import BorradorParseError as _BorradorParseError
from .._schema import ArtefactKind
from .modelo_100_summary_v2025 import Modelo100ObservedV2025Extractor as _Modelo100ObservedV2025Extractor

# The generic observed-value extraction algorithm is year-stable from 2021
# onward: the borrador PDF format has not changed the casilla-row layout.
# Separate entries allow callers to pass año_override=2021/2022/2023 without
# BorradorParseError while reusing the same implementation.
_REGISTRY_BY_AÑO: dict[int, type] = {
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
        A freshly-instantiated extractor matching the requested ``año``.

    Raises:
        _BorradorParseError: When no extractor is registered for ``año``.
    """
    cls = _REGISTRY_BY_AÑO.get(año)
    if cls is None:
        known = sorted(_REGISTRY_BY_AÑO.keys())
        raise _BorradorParseError(f"no Modelo 100 observed-value extractor for año={año}; supported: {known}")
    return cls()


__all__ = ["ArtefactKind", "get_extractor"]
