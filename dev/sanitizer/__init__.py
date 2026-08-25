"""Public API for the AEAT PDF sanitiser.

Strips PII from real AEAT PDFs so the sanitised output can be committed as a
regression-test fixture. The sanitisation strategy is *token replacement*:
every cleartext PII value listed in a :class:`TokenMap` is rewritten in place,
preserving layout, fonts, and page count. The deep-extractor contract requires
this because blackout-style redaction would delete the text the extractor parses
against.

This package is fixture-preparation infrastructure, not runtime filing import
or general-purpose anonymisation. Cleartext mappings belong in operator-local
scratch files; the committed artefact should be the sanitised PDF plus the
cleartext-free audit output from :class:`SanitizationResult`.

Callers outside :mod:`dev.sanitizer` must import
exclusively from this module — the private modules
(``_records``, ``errors``, ``_pipeline``, ``_streams``,
``_metadata``, ``_dynamic``, ``_structtree``, ``_determinism``,
``_residual_identity``) are implementation details.

Examples:
    >>> from dev.sanitizer import sanitize_pdf, TokenMap, NifReplacement  # doctest: +SKIP
    >>> mapping = TokenMap(  # doctest: +SKIP
    ...     nif=(NifReplacement(real="Y1234567X", synthetic="Y0000001S", surface_label="taxpayer NIE"),),
    ... )
    >>> result = sanitize_pdf(source_bytes, mapping)  # doctest: +SKIP
"""

from __future__ import annotations

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
from ._residual_identity import (
    CHECKSUM_VERIFIED_KINDS,
    ResidualFinding,
    ResidualKind,
    accounted_for_values,
    checksum_valid_spans,
    scan_for_residual_identities,
)

__all__ = [
    "CHECKSUM_VERIFIED_KINDS",
    "SANITIZER_VERSION",
    "AddressReplacement",
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
    "ResidualFinding",
    "ResidualKind",
    "SanitizationResult",
    "SanitizationWarning",
    "ScrubbedSurface",
    "TokenMap",
    "accounted_for_values",
    "checksum_valid_spans",
    "sanitize_pdf",
    "scan_for_residual_identities",
]
