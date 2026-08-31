"""Shared primitives for the project's PDF-import families.

The :mod:`adapters.inbound.pdf` package is the small coordination layer behind
the concrete PDF parser packages. Declaracion and borrador parsers use its
casilla-bearing records and label-regex helpers; justificante parsers use the
shared error root and text/provenance helpers while remaining receipt-only
metadata parsers. Callers should still import from the concrete
:mod:`adapters.inbound.declaracion`, :mod:`adapters.inbound.borrador`, or
:mod:`adapters.inbound.justificante` packages.

Public symbols:

- :class:`ExtractedCasilla` -- one casilla ID plus the printed value and
  extraction provenance from a casilla-complete PDF.
- :class:`PdfModeloImportError` -- base exception for PDF-import parsing errors.
- :class:`LabelHit`, :func:`apply_label_regex`, and
  :func:`parse_spanish_decimal` -- label-anchored extraction helpers used by
  declaracion and borrador parsers.
- :func:`extract_pages_text_from_path`, :func:`extract_pages_text_from_bytes`,
  :func:`extract_pages_text_concatenated`, and
  :func:`extract_pages_text_with_fast_path` -- shared pdfplumber-backed
  page-text extraction primitives.
- :func:`sha256_file` and :func:`source_pdf_reference_path` -- shared
  source-provenance helpers (digest and redacted reference path).

See Also:
    - :mod:`adapters.inbound.declaracion` for registry-grounded filed
      declaration parsing.
    - :mod:`adapters.inbound.borrador` for borrador/Renta artefact parsing.
    - :mod:`adapters.inbound.justificante` for AEAT filing-receipt parsing.
"""

from __future__ import annotations

from ....domain.justificante import PdfModeloImportError
from .extracted_casilla import ExtractedCasilla
from .label_regex import (
    EJERCICIO_LABEL,
    MODELO_LABEL,
    PRESENTADOR_NIF_LABEL,
    SPANISH_AMOUNT_GROUP,
    TEXT_VALUE_GROUP,
    LabelHit,
    apply_label_regex,
    parse_spanish_decimal,
)
from .page_text_extraction import (
    extract_pages_text_concatenated,
    extract_pages_text_from_bytes,
    extract_pages_text_from_path,
    extract_pages_text_with_fast_path,
)
from .utils import sha256_file, source_pdf_reference_path

__all__ = [
    "EJERCICIO_LABEL",
    "MODELO_LABEL",
    "PRESENTADOR_NIF_LABEL",
    "SPANISH_AMOUNT_GROUP",
    "TEXT_VALUE_GROUP",
    "ExtractedCasilla",
    "LabelHit",
    "PdfModeloImportError",
    "apply_label_regex",
    "extract_pages_text_concatenated",
    "extract_pages_text_from_bytes",
    "extract_pages_text_from_path",
    "extract_pages_text_with_fast_path",
    "parse_spanish_decimal",
    "sha256_file",
    "source_pdf_reference_path",
]
