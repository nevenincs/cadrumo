"""Inert namespace for the shared PDF-import primitives package.

This package exports nothing. Every contract below has one canonical defining
module, and callers -- inside the package and out -- import it from there.

Where the contracts live:

- Casilla-bearing records -- ``extracted_casilla``, defining
  :class:`ExtractedCasilla`: one casilla ID plus the printed value and the
  extraction provenance read off a casilla-complete PDF.
- Label-anchored extraction -- ``label_regex``, defining :class:`LabelHit`,
  ``apply_label_regex``, ``parse_spanish_decimal``, and the ``EJERCICIO_LABEL``,
  ``MODELO_LABEL``, ``PRESENTADOR_NIF_LABEL``, ``SPANISH_AMOUNT_GROUP`` and
  ``TEXT_VALUE_GROUP`` fragments the declaracion and borrador parsers anchor on.
- Page text -- ``page_text_extraction``, defining the pdfplumber-backed
  ``extract_pages_text_from_path``, ``extract_pages_text_from_bytes``,
  ``extract_pages_text_concatenated`` and ``extract_pages_text_with_fast_path``
  primitives.
- Source provenance -- ``source_provenance``, defining ``sha256_file`` and
  ``source_pdf_reference_path``, the digest and redacted reference path that keep
  the operator's local filename out of persisted provenance at the
  secure-storage boundary.

``domain.justificante.errors`` remains the sole canonical source for
:class:`PdfModeloImportError`, the root exception the parsers in this package
raise; it was only ever passed through this namespace and is now imported from
its defining module.

See Also:
    :mod:`adapters.inbound.declaracion`
        Registry-grounded filed declaration parsing.
    :mod:`adapters.inbound.borrador`
        Borrador/Renta artefact parsing.
    :mod:`adapters.inbound.justificante`
        AEAT filing-receipt parsing, receipt-only metadata.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
