"""Shared primitives for the project's PDF-import families (#305 cluster A).

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
from ._shared import ExtractedCasilla

__all__ = [
    "ExtractedCasilla",
    "PdfFilingImportError",
]
