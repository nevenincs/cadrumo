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
``_metadata``, ``_dynamic``, ``_structtree``, ``_determinism``)
are implementation details. ``residual_identity`` is public: two of
its symbols are consumed by :mod:`dev.identity`, and a module reached
from another package cannot be an implementation detail.

Examples:
    >>> from dev.sanitizer import sanitize_pdf, TokenMap, NifReplacement  # doctest: +SKIP
    >>> mapping = TokenMap(  # doctest: +SKIP
    ...     nif=(NifReplacement(real="Y1234567X", synthetic="Y0000001S", surface_label="taxpayer NIE"),),
    ... )
    >>> result = sanitize_pdf(source_bytes, mapping)  # doctest: +SKIP

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
