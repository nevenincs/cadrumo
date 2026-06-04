"""Narrow exceptions for the 036 censo-sync application service.

Every error here surfaces through the ``aeat config profile censo``
verb tree as a typed refusal, covering authentication failures, schema
violations, and apply-path conflicts that the censo-sync service can
encounter against the AEAT Mis Datos Censales endpoint.
"""

from __future__ import annotations

from ...core.errors import AeatError


class CensoSyncError(AeatError):
    """Base for every 036 censo-sync application failure."""


class CensoNotAvailableError(CensoSyncError):
    """Raised when the sede G313 endpoint returns no parseable censo.

    Typical cause: the operator is not yet enrolled in IAE (no alta
    declared), or G313 authentication failed at the AEAT side (e.g.
    the certificate is valid but not registered against the operator's
    NIF in AEAT's censo). The CLI surfaces this with a recovery
    hint pointing at ``aeat config profile create`` or
    ``aeat config auth configure``.
    """


class CensoFieldValidationError(CensoSyncError):
    """Raised when sede G313 returns a value the schema cannot accept.

    Examples: an unknown ``establecimiento_type`` enum, a withholding
    percentage outside the legally-declared {15, 7, 1} set, a malformed
    catastral reference. The error names the offending field and the
    rejected value so the operator can raise it with AEAT support; the
    snapshot is NOT persisted on this path.
    """


class CensoApplyConflictError(CensoSyncError):
    """Raised when ``apply`` aborts because a dependent's state cannot be safely stamped.

    Examples: an in-flight workflow run on a dependent work unit, a
    filing record currently being amended, a draft mid-approval. The
    apply path refuses cleanly so the operator can resolve the
    in-flight state first; partial cross-validation that leaves some
    dependents stamped and others unstamped would silently corrupt
    the legal-source-of-truth invariant the censo lifecycle enforces.
    """


__all__ = [
    "CensoApplyConflictError",
    "CensoFieldValidationError",
    "CensoNotAvailableError",
    "CensoSyncError",
]
