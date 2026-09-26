"""Carry a stored profile record forward to the current profile schema on open.

The persistence half lives on
:meth:`~cadrumo.application.user_profile.capsule_record.ProfileRecordStore.migrate_legacy_schema`;
this module owns the custody lock around it and the invocation-scoped staging
of what the migration cleared, so the entrypoint that opened the profile can
tell the operator once, on that first open.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path

from ...core.paths import effective_storage_root
from ...core.time.clock import now as _utc_now
from ...domain.user_profile.schema_migration import ProfileSchemaMigration
from .capsule_record import ProfileRecordSession, ProfileRecordStore
from .custody_repository import profile_custody_transaction_lock

_STAGED_CLEARED_PATHS: ContextVar[tuple[str, ...]] = ContextVar(
    "cadrumo_profile_schema_migration_cleared_paths",
    default=(),
)


def migrate_profile_record_on_open(
    session: ProfileRecordSession,
    *,
    root: Path | None = None,
) -> ProfileSchemaMigration | None:
    """Migrate the session's stored record under the custody lock; ``None`` if current.

    Every cleared payer-fact path is staged for this invocation's notices.
    """
    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, session.profile_id):
        migration = ProfileRecordStore(session=session, root=storage_root).migrate_legacy_schema(now=_utc_now())
    if migration is not None and migration.cleared_paths:
        staged = set(_STAGED_CLEARED_PATHS.get()) | set(migration.cleared_paths)
        _STAGED_CLEARED_PATHS.set(tuple(sorted(staged)))
    return migration


def drain_migration_cleared_paths() -> tuple[str, ...]:
    """Return and clear the payer-fact paths a migration in this invocation cleared."""
    staged = _STAGED_CLEARED_PATHS.get()
    if staged:
        _STAGED_CLEARED_PATHS.set(())
    return staged


__all__ = [
    "drain_migration_cleared_paths",
    "migrate_profile_record_on_open",
]
