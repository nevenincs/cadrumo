"""Shared primitives for the project's PDF-import families (#305).

The :mod:`aeat._pdf_import` package owns types and errors that every
per-PDF-class module under :mod:`aeat.justificante`, :mod:`aeat.declaracion`,
:mod:`aeat.borrador`, and :mod:`aeat.predeclaracion` consumes. It is
*deliberately underscore-prefixed* because the concrete parsing modules
are the public surface; callers from outside the project should not
need to import from here.

Public symbols:

- :class:`ExtractedCasilla` — one casilla ID + printed value tuple produced
  by any PDF-class extractor.
- :class:`PdfFilingImportError` — base exception for every PDF-import
  parsing error.
"""

from __future__ import annotations

from ._errors import PdfFilingImportError
from ._label_regex import (
    SPANISH_AMOUNT_GROUP,
    LabelHit,
    apply_label_regex,
    parse_spanish_decimal,
)
from ._shared import ExtractedCasilla

__all__ = [
    "SPANISH_AMOUNT_GROUP",
    "ExtractedCasilla",
    "LabelHit",
    "PdfFilingImportError",
    "apply_label_regex",
    "parse_spanish_decimal",
]
