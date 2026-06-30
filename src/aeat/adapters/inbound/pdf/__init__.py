"""Shared primitives for the project's PDF-import families.

The :mod:`aeat.adapters.inbound.pdf` package is the small coordination layer
behind the concrete PDF parser packages. Declaracion and borrador parsers use
its casilla-bearing records and label-regex helpers; justificante parsers use
the shared error root and text/provenance helpers while remaining receipt-only
metadata parsers. Callers should still import from the concrete
:mod:`aeat.adapters.inbound.declaracion`,
:mod:`aeat.adapters.inbound.borrador`, or
:mod:`aeat.adapters.inbound.justificante` packages.

Public symbols:

- :class:`~aeat.adapters.inbound.pdf.ExtractedCasilla` -- one casilla ID plus
  the printed value and extraction provenance from a casilla-complete PDF.
- :class:`~aeat.adapters.inbound.pdf.PdfModeloImportError` -- base exception
  for PDF-import parsing errors.
- :class:`~aeat.adapters.inbound.pdf.LabelHit`,
  :func:`~aeat.adapters.inbound.pdf.apply_label_regex`, and
  :func:`~aeat.adapters.inbound.pdf.parse_spanish_decimal` -- label-anchored
  extraction helpers used by declaracion and borrador parsers.

See Also:
    - :mod:`aeat.adapters.inbound.declaracion` for registry-grounded filed
      declaration parsing.
    - :mod:`aeat.adapters.inbound.borrador` for borrador/Renta artefact parsing.
    - :mod:`aeat.adapters.inbound.justificante` for AEAT filing-receipt parsing.
"""

from __future__ import annotations

from ....domain.justificante import PdfModeloImportError
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
    "PdfModeloImportError",
    "apply_label_regex",
    "parse_spanish_decimal",
]
