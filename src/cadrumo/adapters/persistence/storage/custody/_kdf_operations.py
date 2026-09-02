"""The operations the supervised key-derivation child accepts.

One vocabulary that the producer and the validator each wrote out. The supervisor
builds the operation token, and the worker both dispatches on it and checks the
payload's required fields against it, so the two wrap tokens and the two unwrap tokens
appeared twice each in two modules.

Deliberately stdlib-only. Every wrap and unwrap spawns a fresh interpreter to perform
one Argon2id hash, so anything on the worker's import path is paid on the production
login path; this module imports nothing but ``enum`` and ``typing`` and so is safe to
sit there.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = ["UNWRAP_OPERATIONS", "WRAP_OPERATIONS", "KdfOperation"]


class KdfOperation(StrEnum):
    """What the child is being asked to do.

    The tokens are a wire contract between two processes, carried in the JSON the
    supervisor writes to the child's stdin, so their spelling is fixed.
    """

    CALIBRATE = "calibrate-v1"
    """Measure this machine's Argon2id cost; derives nothing and unwraps nothing."""

    PASSWORD_UNWRAP = "password-unwrap-v1"  # noqa: S105 - an operation name, not a credential
    """Unwrap a DEK using the profile's own password."""

    RECOVERY_UNWRAP = "recovery-unwrap-v1"
    """Unwrap a DEK using a recovery secret."""

    PASSWORD_WRAP = "password-wrap-v1"  # noqa: S105 - an operation name, not a credential
    """Wrap a DEK under the profile's own password."""

    RECOVERY_WRAP = "recovery-wrap-v1"
    """Wrap a DEK under a recovery secret."""


UNWRAP_OPERATIONS: Final[frozenset[KdfOperation]] = frozenset(
    {KdfOperation.PASSWORD_UNWRAP, KdfOperation.RECOVERY_UNWRAP},
)
"""The operations that unwrap a DEK, and so require a wrapped DEK in the payload."""

WRAP_OPERATIONS: Final[frozenset[KdfOperation]] = frozenset(
    {KdfOperation.PASSWORD_WRAP, KdfOperation.RECOVERY_WRAP},
)
"""The operations that wrap a DEK, and so require a plain DEK in the payload.

Kept separate from :data:`UNWRAP_OPERATIONS` rather than derived from it: the two
demand different required fields, and a single set with a direction flag would let one
payload shape satisfy the other's check.
"""
