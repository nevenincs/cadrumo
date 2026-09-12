"""Inward operator-scope capabilities for application-layer tests.

The application suites exercise policy and orchestration through the same
translated capability contract as production.  The fake deliberately carries
only application DTOs; concrete bucket paths, lock records, and live-session
objects stay in the persistence adapter tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cadrumo.application.auth.operator_scope_ports import (
    OperatorScopeBucketPaths,
    OperatorScopePorts,
    OperatorScopeSession,
    OperatorScopeStorageError,
)
from cadrumo.application.user_profile.profile_pointer import observe_active_profile_pointer
from cadrumo.core.config import load_settings


@dataclass(slots=True)
class InwardOperatorScopeStorage:
    """No-op lock capability with application-owned path facts."""

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

    def block(self, bucket_id: str) -> None:
        """Make one test bucket fail closed on its next lock acquisition."""
        self.blocked_bucket_ids.add(bucket_id)

    def unblock(self, bucket_id: str) -> None:
        """Release a test-only synthetic lock."""
        self.blocked_bucket_ids.discard(bucket_id)


@dataclass(slots=True)
class InwardOperatorScopeSession:
    """Session capability backed by an explicit translated test session."""

    session: OperatorScopeSession | None
    follows_active_route: bool = False

    def current(self) -> OperatorScopeSession | None:
        if self.follows_active_route:
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
        return self.session

    def serves_bucket(self, session: OperatorScopeSession | None, bucket_id: str) -> bool:
        return session is not None and session.bucket_id == bucket_id


def build_inward_operator_scope_ports(*, session: OperatorScopeSession | None) -> OperatorScopePorts:
    """Build an application-only scope fake for one test-owned session."""
    return OperatorScopePorts(
        storage=InwardOperatorScopeStorage(),
        session=InwardOperatorScopeSession(session),
    )


def build_inward_operator_scope_ports_for_active_route() -> OperatorScopePorts:
    """Build a fake session from the application-owned active-profile route.

    This is useful for real application integration tests that already select
    a profile through the application profile-pointer seam.  It does not read
    or expose a persistence ``BucketSession``.
    """
    return OperatorScopePorts(
        storage=InwardOperatorScopeStorage(),
        session=InwardOperatorScopeSession(session=None, follows_active_route=True),
    )


__all__ = [
    "InwardOperatorScopeSession",
    "InwardOperatorScopeStorage",
    "build_inward_operator_scope_ports",
    "build_inward_operator_scope_ports_for_active_route",
]
