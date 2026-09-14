"""Inward operator-scope fake for AEAT-sync application tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ....core.config import load_settings
from ...auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
    OperatorScopeStorageError,
)
from ...user_profile.profile_pointer import observe_active_profile_pointer


@dataclass(slots=True)
class _Storage:
    blocked_bucket_ids: set[str] = field(default_factory=set)

    def resolve(self, root: Path, bucket_id: str) -> OperatorScopeBucketPaths:
        return OperatorScopeBucketPaths(bucket_id=bucket_id, bucket_dir=root / "buckets" / bucket_id)

    def acquire_lock(self, paths: OperatorScopeBucketPaths, *, wait_seconds: float) -> None:
        del wait_seconds
        if paths.bucket_id in self.blocked_bucket_ids:
            raise OperatorScopeStorageError(
                operation="acquire_lock",
                bucket_id=paths.bucket_id,
                failure_kind="busy",
            )

    def release_lock(self, paths: OperatorScopeBucketPaths) -> None:
        del paths


@dataclass(slots=True)
class _ActiveRouteSession:
    session: OperatorScopeSession | None = None

    def current(self) -> OperatorScopeSession | None:
        settings = load_settings()
        bucket_id = (settings.cadrumo_active_profile or "").strip()
        if not bucket_id:
            bucket_id = observe_active_profile_pointer(settings.cadrumo_local_storage_root).bucket_id or ""
        if not bucket_id:
            return None
        resolved = OperatorScopeSession(
            bucket_id=bucket_id,
            storage_root=settings.cadrumo_local_storage_root,
        )
        if self.session == resolved:
            return self.session
        self.session = resolved
        return resolved

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> bool:
        return session is not None and session.bucket_id == bucket_id


def build_inward_operator_scope_ports_for_active_route() -> OperatorScopePorts:
    """Build an application-only scope fake from the active-profile route."""
    return OperatorScopePorts(storage=_Storage(), session=_ActiveRouteSession())


__all__ = ["build_inward_operator_scope_ports_for_active_route"]
