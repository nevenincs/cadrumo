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

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing, so an
import is written against the defining module rather than against this one.
``residual_identity`` is reached from :mod:`dev.identity` and so is public in
that same sense: a module another package imports is not an implementation
detail.

Examples:
    >>> from dev.sanitizer._pipeline import sanitize_pdf  # doctest: +SKIP
    >>> from dev.sanitizer._records import NifReplacement, TokenMap  # doctest: +SKIP
    >>> mapping = TokenMap(  # doctest: +SKIP
    ...     nif=(NifReplacement(real="Y1234567X", synthetic="Y0000001S", surface_label="taxpayer NIE"),),
    ... )
    >>> result = sanitize_pdf(source_bytes, mapping)  # doctest: +SKIP
"""
