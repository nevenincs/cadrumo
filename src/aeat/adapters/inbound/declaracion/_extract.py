"""Extraction primitives for declaración PDFs — thin wrappers.

The concrete primitives live in :mod:`aeat.adapters.inbound.pdf._label_regex`;
this module re-exports the subset that declaración extractors consume.
Kept for backwards-compatible import paths.
"""

from __future__ import annotations

from ..pdf._label_regex import (
    SPANISH_AMOUNT_GROUP as _SPANISH_AMOUNT_GROUP,
)
from ..pdf._label_regex import (
    LabelHit as LabelExtractionHit,
)
from ..pdf._label_regex import (
    apply_label_regex,
    parse_spanish_decimal,
)

__all__ = [
    "_SPANISH_AMOUNT_GROUP",
    "LabelExtractionHit",
    "apply_label_regex",
    "parse_spanish_decimal",
]
