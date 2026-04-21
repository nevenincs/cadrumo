"""Per-año Modelo 100 summary-block extractor registry."""

from __future__ import annotations

from .._errors import BorradorParseError
from .._schema import ArtefactKind
from .modelo_100_summary_v2025 import Modelo100SummaryV2025Extractor

_REGISTRY_BY_AÑO: dict[int, type] = {
    2025: Modelo100SummaryV2025Extractor,
}


def get_extractor(año: int) -> Modelo100SummaryV2025Extractor:
    """Return a fresh Modelo 100 summary extractor for the given tax year."""
    cls = _REGISTRY_BY_AÑO.get(año)
    if cls is None:
        known = sorted(_REGISTRY_BY_AÑO.keys())
        raise BorradorParseError(f"no Modelo 100 summary extractor for año={año}; supported: {known}")
    return cls()


__all__ = ["ArtefactKind", "get_extractor"]
