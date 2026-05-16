"""Narrow exceptions for the 036 census-sync application service.

Backs the W85.S2349 census-sync wave per the 2026-05-16 amendment to
the modelo-036-037-foundation ADR. Every error here surfaces through
the ``aeat config profile census`` verb tree as a typed refusal.
"""

from __future__ import annotations

from ...core.errors import AeatError


class CensusSyncError(AeatError):
    """Base for every 036 census-sync application failure."""


class CensusNotAvailableError(CensusSyncError):
    """Raised when the sede G313 endpoint returns no parseable census.

    Typical cause: the operator is not yet enrolled in IAE (no alta
    declared), or G313 authentication failed at the AEAT side (e.g.
    the certificate is valid but not registered against the operator's
    NIF in AEAT's census). The CLI surfaces this with a recovery
    hint pointing at ``aeat config profile init`` or
    ``aeat config auth configure``.
    """


class CensusFieldValidationError(CensusSyncError):
    """Raised when sede G313 returns a value the schema cannot accept.

    Examples: an unknown ``establecimiento_type`` enum, a withholding
    percentage outside the legally-declared {15, 7, 1} set, a malformed
    catastral reference. The error names the offending field and the
    rejected value so the operator can raise it with AEAT support; the
    snapshot is NOT persisted on this path.
    """


class CensusApplyConflictError(CensusSyncError):
    """Raised when ``apply`` aborts because a dependent's state cannot
    be safely stamped.

    Examples: an in-flight workflow run on a dependent work unit, a
    filing record currently being amended, a draft mid-approval. The
    apply path refuses cleanly so the operator can resolve the
    in-flight state first; partial cross-validation that leaves some
    dependents stamped and others unstamped would silently corrupt
    the legal-source-of-truth invariant the ADR amendment locks.
    """


__all__ = [
    "CensusApplyConflictError",
    "CensusFieldValidationError",
    "CensusNotAvailableError",
    "CensusSyncError",
]
