"""Public API for the AEAT PDF sanitiser.

Strips PII from real AEAT justificante PDFs so the sanitised output
can be committed as a regression-test fixture. The sanitisation
strategy is *token replacement* — every cleartext PII value listed
in a :class:`TokenMap` is rewritten in-place, preserving layout,
fonts, and page count. The deep-extractor contract requires this:
blackout-style redaction would delete the text the extractor parses
against.

Callers outside :mod:`aeat.adapters.inbound.sanitizer` must import
exclusively from this module — the private modules
(``_records``, ``_errors``, ``_pipeline``, ``_streams``,
``_metadata``, ``_dynamic``, ``_structtree``, ``_determinism``)
are implementation details.

Examples:
    >>> from aeat.adapters.inbound.sanitizer import sanitize_pdf, TokenMap, NifReplacement  # doctest: +SKIP
    >>> mapping = TokenMap(  # doctest: +SKIP
    ...     nif=(NifReplacement(real="Y1234567X", synthetic="Y0000001S", surface_label="taxpayer NIE"),),
    ... )
    >>> result = sanitize_pdf(source_bytes, mapping)  # doctest: +SKIP
"""

from __future__ import annotations

from ._errors import (
    AlreadySanitizedError,
    SanitizationError,
    SanitizerSourceParseError,
    SignaturePresentError,
    UnknownSurfaceError,
)
from ._pipeline import SANITIZER_VERSION, sanitize_pdf
from ._records import (
    AddressReplacement,
    ArbitraryReplacement,
    CsvReplacement,
    DeterminismFlags,
    ExpedienteReplacement,
    IbanReplacement,
    ImporteReplacement,
    NameReplacement,
    NifReplacement,
    NrcReplacement,
    Replacement,
    SanitizationResult,
    SanitizationWarning,
    ScrubbedSurface,
    TokenMap,
)

__all__ = [
    "SANITIZER_VERSION",
    "AddressReplacement",
    "AlreadySanitizedError",
    "ArbitraryReplacement",
    "CsvReplacement",
    "DeterminismFlags",
    "ExpedienteReplacement",
    "IbanReplacement",
    "ImporteReplacement",
    "NameReplacement",
    "NifReplacement",
    "NrcReplacement",
    "Replacement",
    "SanitizationError",
    "SanitizationResult",
    "SanitizationWarning",
    "SanitizerSourceParseError",
    "ScrubbedSurface",
    "SignaturePresentError",
    "TokenMap",
    "UnknownSurfaceError",
    "sanitize_pdf",
]
