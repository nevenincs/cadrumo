"""Typed error hierarchy for corpus-manifest validation.

Defines the leaf exceptions raised by the corpus-manifest loader and
verifier. All inherit from :class:`core.errors.CadrumoError` so any
caller catching the framework's base error type also catches manifest
failures.
"""

from __future__ import annotations

from ..errors.hierarchy import CadrumoError


class CorpusManifestError(CadrumoError, ValueError):
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


class CorpusBundleError(CorpusManifestError):
    """Base error for corpus bundle build/verify failures.

    Raised for structural bundle problems (not a zip archive, missing or
    structurally invalid embedded manifest, unsupported manifest
    version) that are distinct from a checksum-level verification
    failure (:class:`CorpusBundleVerificationError`).
    """


class CorpusBundleVerificationError(CorpusBundleError):
    """Raised when a bundle's embedded manifest does not match its archived files.

    Carries the same missing/unexpected/mismatched vocabulary as
    :class:`CorpusManifestDriftError` so a bundle-integrity failure and a
    live-corpus-drift failure read the same way to an operator; the
    distinguishing detail is that this failure is about a zip archive's
    contents, not the corpus already on disk.
    """


__all__ = [
    "CorpusBundleError",
    "CorpusBundleVerificationError",
    "CorpusManifestDriftError",
    "CorpusManifestError",
    "CorpusManifestTamperError",
]
