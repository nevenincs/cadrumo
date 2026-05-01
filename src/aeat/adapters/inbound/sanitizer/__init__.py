"""Public API for the AEAT PDF sanitiser (#239).

This subpackage strips PII from real AEAT justificante PDFs so the
sanitised output can be committed as a regression-test fixture.
The sanitisation strategy is *token replacement* — every cleartext
PII value listed in a :class:`TokenMap` is rewritten in-place
preserving layout, fonts, and page count. The deep-extractor
contract requires this: blackout-style redaction would delete the
text the extractor parses against.

The full architectural rationale, threat model, and 8-step order
of operations live in
``.vault/adr/2026-04-25-pdf-sanitizer-adr.md``. Callers outside
:mod:`aeat.adapters.inbound.sanitizer` must import exclusively from this module —
the private ``_records``, ``_errors``, ``_pipeline``, ``_streams``,
``_metadata``, ``_dynamic``, ``_structtree``, ``_determinism``
modules are implementation details.

Example:
    >>> from aeat.adapters.inbound.sanitizer import sanitize_pdf, TokenMap, NifReplacement  # doctest: +SKIP
    >>> mapping = TokenMap(  # doctest: +SKIP
    ...     nif=(NifReplacement(real="Y4113523X", synthetic="Y0000001Z", surface_label="taxpayer NIE"),),
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
