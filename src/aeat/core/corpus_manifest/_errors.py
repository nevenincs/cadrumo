"""Typed error hierarchy for corpus-manifest validation.

Defines the leaf exceptions raised by the corpus-manifest loader and
verifier. All inherit from :class:`aeat.core.errors.AeatError` so any
caller catching the framework's base error type also catches manifest
failures.
"""

from __future__ import annotations

from ..errors import AeatError


class CorpusManifestError(AeatError, ValueError):
    """Base error for any failure in corpus-manifest parsing or validation.

    Concrete failure modes derive from this class; callers can catch
    :class:`CorpusManifestError` to handle every manifest failure
    uniformly, or catch a leaf such as :class:`CorpusManifestTamperError`
    to react to a specific condition.
    """


class CorpusManifestTamperError(CorpusManifestError):
    """Raised when a manifest's self-attesting digest does not match its body.

    Indicates the manifest body has been edited without recomputing the
    embedded checksum — usually a sign of corruption or tampering rather
    than legitimate drift between the manifest and the on-disk corpus
    (which is signalled by :class:`CorpusManifestDriftError`).
    """


class CorpusManifestDriftError(CorpusManifestError):
    """Raised when the on-disk corpus diverges from the manifest's expectations.

    Distinct from :class:`CorpusManifestTamperError`: the manifest itself
    is internally consistent, but the files it describes have been
    added, removed, or modified relative to the manifest's recorded
    digests.
    """


__all__ = [
    "CorpusManifestDriftError",
    "CorpusManifestError",
    "CorpusManifestTamperError",
]
