"""Modelo 100 (IRPF annual) casilla-complete extractor (#239).

Exposes the three concrete extractor classes — one per supported
template revision — that the declaración registry at
``_extractors/__init__.py`` imports and registers.
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
