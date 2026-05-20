"""Errors raised by the workspace-initialization application service."""

from __future__ import annotations

from ...core.errors import AeatError


class WorkspaceBucketTornError(AeatError):
    """Raised when a bucket manifest exists without its encrypted profile record.

    The disaster ADR (Ruling 3) sequences profile creation as five
    ordered writes: directory tree, manifest, transient session,
    encrypted ``UserProfileRecord``, active-profile pointer. A crash
    between the manifest write (step 2) and the record write (step 4)
    leaves a *torn* bucket: the manifest scan reports the profile as
    existing, but no decryptable profile record backs it.

    ``initialize_workspace`` distinguishes this from a benign idempotent
    re-run with a no-decryption DB-existence check
    (``UserProfileLifecycleRepository.exists``). A genuine re-run finds
    the record and proceeds; a torn bucket finds the manifest but not
    the record and raises this error so the operator routes through an
    explicit repair verb rather than silently mixing new profile data
    into degraded storage.
    """


__all__ = ["WorkspaceBucketTornError"]
