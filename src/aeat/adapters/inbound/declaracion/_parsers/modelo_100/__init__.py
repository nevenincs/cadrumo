"""Modelo 100 (IRPF annual) casilla-complete extractor.

Exposes the three concrete extractor classes — one per supported
template revision (2021 legacy, 2022 modern, 2023 modern) — that the
declaración registry under
:mod:`aeat.adapters.inbound.declaracion._extractors` imports and
registers. The implementation lives in :mod:`._extractor`; this package
initializer exposes the parser package surface.
"""

from __future__ import annotations

from ._extractor import (
    Modelo100V2021LegacyExtractor,
    Modelo100V2022ModernExtractor,
    Modelo100V2023ModernExtractor,
)

__all__ = [
    "Modelo100V2021LegacyExtractor",
    "Modelo100V2022ModernExtractor",
    "Modelo100V2023ModernExtractor",
]
