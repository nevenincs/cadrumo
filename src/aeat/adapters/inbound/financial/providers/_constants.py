"""Shared file-extension constants for financial-provider detection.

Single authoritative source for the extension sets that route
:func:`_detection.provider_for_extension` and
``_detection._ordered_candidates``, and for the
:attr:`~_base.FinancialProvider.supported_extensions` declarations on
each concrete provider class.

Keeping these constants in one place ensures that the detection
router and the provider contract never drift: adding a new alias (e.g.
``.tsv`` for CSV-shaped input) requires one edit here rather than one
edit in every dispatch branch.
"""

from __future__ import annotations

from .....core.external_constants import PDF_EXTENSION, XLSX_EXTENSION

CSV_EXTENSIONS: frozenset[str] = frozenset({".csv", ".txt"})
"""File extensions treated as CSV-compatible input by the CSV provider."""

__all__ = ["CSV_EXTENSIONS", "PDF_EXTENSION", "XLSX_EXTENSION"]
