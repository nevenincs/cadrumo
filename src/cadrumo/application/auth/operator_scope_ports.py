"""Application-owned ports for operator auth storage scoping.

Operator auth policy needs only a narrow bucket-path/lock surface and a
read-only observation of the currently bound custody session.  The concrete
filesystem paths, lock records, and live session objects remain owned by the
outward persistence adapters; this module carries the translated records and
the capability bundle that application callers require.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError


@dataclass(frozen=True, slots=True)
class OperatorScopeBucketPaths:
    """The path facts required to lock one operator-auth bucket."""

    bucket_id: str
    bucket_dir: Path


@dataclass(frozen=True, slots=True)
class OperatorScopeSession:
    """The non-secret identity facts of the currently bound custody session."""

    bucket_id: str
    storage_root: Path | None


class OperatorScopeStoragePort(Protocol):
    """Resolve and lock a bucket without exposing persistence DTOs."""

    def resolve(self, root: Path, bucket_id: str) -> OperatorScopeBucketPaths:
        """Resolve the bucket directory used by the auth mutation lock."""
        ...

    def acquire_lock(self, paths: OperatorScopeBucketPaths, *, wait_seconds: float) -> None:
        """Acquire the bucket lock or raise an application storage error."""
        ...

    def release_lock(self, paths: OperatorScopeBucketPaths) -> None:
        """Release the bucket lock owned by the current auth mutation."""
        ...


class OperatorScopeSessionPort(Protocol):
    """Observe and compare the live custody session for one auth operation."""

    def current(self) -> OperatorScopeSession | None:
        """Return the translated current session, if one is bound."""
        ...

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> bool:
        """Return whether the supplied session serves the exact bucket."""
        ...


@dataclass(frozen=True, slots=True)
class OperatorScopePorts:
    """Required outward capabilities for operator auth storage scope policy."""

    storage: OperatorScopeStoragePort
    session: OperatorScopeSessionPort


class OperatorScopeStorageError(CadrumoError):
    """Translated failure from bucket path or lock persistence."""

    def __init__(self, *, operation: str, bucket_id: str, failure_kind: str) -> None:
        """Carry only stable application-safe storage failure facts."""
        self.operation = operation
        self.bucket_id = bucket_id
        self.failure_kind = failure_kind
        super().__init__(f"operator auth storage operation {operation!r} failed")


class OperatorScopeSessionError(CadrumoError):
    """Translated failure while observing the active custody session."""


__all__ = [
    "OperatorScopeBucketPaths",
    "OperatorScopePorts",
    "OperatorScopeSession",
    "OperatorScopeSessionError",
    "OperatorScopeSessionPort",
    "OperatorScopeStorageError",
    "OperatorScopeStoragePort",
]
