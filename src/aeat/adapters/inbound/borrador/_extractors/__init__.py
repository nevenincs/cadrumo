"""Per-año Modelo 100 observed-value extractor registry.

Registers the concrete extractor classes (one per tax year) and exposes
:func:`get_extractor` for the public
:func:`aeat.adapters.inbound.borrador.parse_borrador` entry point.
"""

from __future__ import annotations

from .._errors import BorradorParseError as _BorradorParseError
from .._schema import ArtefactKind
from .modelo_100_summary_v2025 import Modelo100ObservedV2025Extractor as _Modelo100ObservedV2025Extractor

_REGISTRY_BY_AÑO: dict[int, type] = {
    2025: _Modelo100ObservedV2025Extractor,
}


def get_extractor(año: int) -> _Modelo100ObservedV2025Extractor:
    """Return a fresh Modelo 100 observed-value extractor for the given tax year.

    Args:
        año: The four-digit tax year for which an extractor is required.

    Returns:
        A freshly-instantiated extractor matching the requested ``año``.

    Raises:
        :exc:`aeat.adapters.inbound.borrador._errors.BorradorParseError`:
            When no extractor is registered for ``año``.
    """
    cls = _REGISTRY_BY_AÑO.get(año)
    if cls is None:
        known = sorted(_REGISTRY_BY_AÑO.keys())
        raise _BorradorParseError(f"no Modelo 100 observed-value extractor for año={año}; supported: {known}")
    return cls()


__all__ = ["ArtefactKind", "get_extractor"]
