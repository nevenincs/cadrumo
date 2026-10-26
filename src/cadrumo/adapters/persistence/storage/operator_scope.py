"""Persistence adapters for the application operator-scope ports."""

from __future__ import annotations

from pathlib import Path

from ....application.auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
    OperatorScopeStorageError,
)
from .bucket.directory_layout import bucket_paths
from .bucket.errors import BucketError
from .bucket.lockfile import acquire_lock, release_lock
from .master_key.active_session import current_active_bucket_session


class _PersistenceOperatorScopeStorage:
    """Translate bucket layout and lock primitives into the app port."""

    def resolve(self, root: Path, bucket_id: str) -> OperatorScopeBucketPaths:
        try:
            paths = bucket_paths(root, bucket_id)
        except BucketError as exc:
            raise OperatorScopeStorageError(
                operation="resolve",
                bucket_id=bucket_id,
                failure_kind=type(exc).__name__,
            ) from exc
        return OperatorScopeBucketPaths(bucket_id=paths.bucket_id, bucket_dir=paths.bucket_dir)

    def acquire_lock(self, paths: OperatorScopeBucketPaths, *, wait_seconds: float) -> None:
        try:
            acquire_lock(paths, wait_seconds=wait_seconds)
        except BucketError as exc:
            raise OperatorScopeStorageError(
                operation="acquire_lock",
                bucket_id=paths.bucket_id,
                failure_kind=type(exc).__name__,
            ) from exc

    def release_lock(self, paths: OperatorScopeBucketPaths) -> None:
        try:
            release_lock(paths)
        except BucketError as exc:
            raise OperatorScopeStorageError(
                operation="release_lock",
                bucket_id=paths.bucket_id,
                failure_kind=type(exc).__name__,
            ) from exc


class _PersistenceOperatorScopeSession:
    """Translate the live persistence session into application-safe facts."""

    def current(self) -> OperatorScopeSession | None:
        session = current_active_bucket_session()
        if session is None:
            return None
        return OperatorScopeSession(
            bucket_id=session.bucket_id,
            storage_root=session.storage_root,
        )

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> bool:
        return session is not None and session.bucket_id == bucket_id


def build_operator_scope_ports() -> OperatorScopePorts:
    """Build the translated operator-scope capability bundle."""
    return OperatorScopePorts(
        storage=_PersistenceOperatorScopeStorage(),
        session=_PersistenceOperatorScopeSession(),
    )


__all__ = ["build_operator_scope_ports"]
