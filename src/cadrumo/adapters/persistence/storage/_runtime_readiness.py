"""Secure-storage runtime readiness vocabulary.

The typed answer to "why can this process not serve profile-bound storage",
and the refusal that carries it. Separated from :mod:`.runtime` because the
two have different dependency shapes: the runtime INSPECTS the process --
settings, routes, the live bucket session -- while this vocabulary is a closed
enum, three frozen records, and one error builder over nothing but
:mod:`core` and the storage error hierarchy.

That difference is what makes the split load-bearing rather than cosmetic.
:class:`~adapters.persistence.storage.sql.SecureObjectRepository` re-checks
session freshness on every operation and must raise the same refusal the
runtime raises, so it needs this vocabulary -- but it emphatically does not
need the runtime aggregate, and the runtime constructs the repository. Holding
both in one module made that a genuine cycle, which was hidden rather than
removed by a deferred function-local import at each end. A deferred import
postpones a cycle: it survives as an evaluation-order hazard that surfaces as
a partially-initialised module the moment an unrelated edit reorders imports.

With the vocabulary in its own module both sides import it eagerly, at the
seam where the dependency genuinely is, and the cycle is gone rather than
deferred.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from ....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .errors import StorageValidationError


class StorageRuntimeReadinessCode(StrEnum):
    """Machine-readable secure-storage runtime readiness states."""

    READY = "ready"
    NO_ACTIVE_SESSION = "no_active_session"
    SESSION_SEALED = "session_sealed"
    SESSION_EXPIRED = "session_expired"
    UNSECURED_BACKEND = "unsecured_backend"
    ROUTE_NOT_ACTIVE_BUCKET = "route_not_active_bucket"
    ROUTE_BUCKET_MISMATCH = "route_bucket_mismatch"
    SESSION_CHANGED = "session_changed"


class StorageRuntimeReadinessIssue(BaseModel):
    """One reason the runtime is not ready for profile-bound storage."""

    model_config = _STRICT_FROZEN

    code: StorageRuntimeReadinessCode


class StorageRuntimeSession(BaseModel):
    """Key-material-free projection of the active bucket session."""

    model_config = _STRICT_FROZEN

    active: bool
    idle_deadline: datetime
    sealed: bool
    expired: bool
    unsecured_backend: bool


class StorageRuntimeReadiness(BaseModel):
    """Profile-bound storage readiness result."""

    model_config = _STRICT_FROZEN

    ready: bool
    code: StorageRuntimeReadinessCode
    issues: tuple[StorageRuntimeReadinessIssue, ...] = ()


def readiness_issue(*, code: StorageRuntimeReadinessCode) -> StorageRuntimeReadinessIssue:
    """Return one typed readiness issue for ``code``."""
    return StorageRuntimeReadinessIssue(code=code)


def readiness_error(readiness: StorageRuntimeReadiness) -> StorageValidationError:
    """Project typed readiness facts into the registered storage refusal.

    The refusal is locale-neutral: the operator-facing sentence comes from the
    translated message key, and the codes travel as structured context so a
    caller can tell WHICH unready state it met without parsing prose.
    """
    issue_codes = tuple(issue.code.value for issue in readiness.issues)
    return StorageValidationError(
        context={
            "details": readiness.code.value,
            "readiness_code": readiness.code.value,
            "readiness_issue_codes": issue_codes,
        },
        translated_message="errors.storage.runtime.not_ready",
    )


def runtime_not_ready_error(code: StorageRuntimeReadinessCode) -> StorageValidationError:
    """Build a locale-neutral storage-runtime readiness failure for one code."""
    return readiness_error(
        StorageRuntimeReadiness(
            ready=False,
            code=code,
            issues=(StorageRuntimeReadinessIssue(code=code),),
        ),
    )


__all__ = [
    "StorageRuntimeReadiness",
    "StorageRuntimeReadinessCode",
    "StorageRuntimeReadinessIssue",
    "StorageRuntimeSession",
    "readiness_error",
    "readiness_issue",
    "runtime_not_ready_error",
]
