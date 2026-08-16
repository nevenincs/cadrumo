"""Runtime-owned :class:`SecureObjectRepository` factories.

Builds :class:`SecureObjectRepository` instances bound to the active profile's
unlocked storage route, so callers obtain a repository without resolving the
storage namespace or key material themselves.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from ....core.config import Settings, StorageRouteKind, classify_storage_route, load_settings
from ._namespace_registry import STORAGE_NAMESPACE_REGISTRY
from .errors import StorageValidationError
from .runtime import StorageRuntimeReadinessCode, inspect_bucket_storage_runtime, runtime_not_ready_error
from .sql import SecureObjectRepository

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def _active_bucket_id_for_source(
    source: Settings,
    *,
    include_process_pointer: bool,
) -> str | None:
    """Resolve the active bucket for ``source`` without ignoring scoped settings."""
    override = (source.cadrumo_active_profile or "").strip()
    if override:
        return override
    route = classify_storage_route(source)
    if route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE:
        return route.bucket_id
    if include_process_pointer:
        from ....core import resolve_active_bucket_id

        return resolve_active_bucket_id()
    return None


def secure_object_repository_for_bucket(
    bucket_id: str,
    settings: Settings | None = None,
) -> SecureObjectRepository:
    """Return a bucket-attached :class:`SecureObjectRepository` through storage runtime."""
    return inspect_bucket_storage_runtime(bucket_id, settings or load_settings()).secure_object_repository()


def secure_object_repository_for_active_bucket() -> SecureObjectRepository:
    """Return a :class:`SecureObjectRepository` attached to the selected active profile bucket."""
    from ....core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise runtime_not_ready_error(StorageRuntimeReadinessCode.NO_ACTIVE_SESSION)
    return secure_object_repository_for_bucket(bucket_id)


def secure_object_repository_for_active_bucket_or_default_route(
    settings: Settings | None = None,
) -> SecureObjectRepository:
    """Return a :class:`SecureObjectRepository` for the active bucket, or the process default.

    This lower-level storage helper is for repository base classes that
    still support explicit injected/default SQL engines in tests and
    bootstrap-adjacent code. It does not catch active-bucket runtime
    errors: once a bucket is selected, route/session failures surface
    from ``secure_object_repository_for_bucket`` instead of falling
    back to a bare repository.
    """
    source = settings or load_settings()
    bucket_id = _active_bucket_id_for_source(
        source,
        include_process_pointer=settings is None,
    )
    if bucket_id is None:
        from .sql.engine import get_engine

        return SecureObjectRepository(engine=get_engine(source), namespace_registry=STORAGE_NAMESPACE_REGISTRY)
    return secure_object_repository_for_bucket(bucket_id, source)


def secure_object_repository_for_cold_bootstrap_state(
    settings: Settings | None = None,
) -> SecureObjectRepository:
    """Return a :class:`SecureObjectRepository` for cold-root recovery reads.

    This is the narrow bootstrap exception used before any active
    profile bucket pointer exists. Normal profile-bound code must use
    ``secure_object_repository_for_active_bucket`` or
    ``secure_object_repository_for_bucket`` so route/session mismatches
    fail closed at the storage runtime boundary.
    """
    from ....core import resolve_active_bucket_id

    source = settings or load_settings()
    route = classify_storage_route(source)
    if route.kind is StorageRouteKind.EXPLICIT_DATABASE_URL:
        raise StorageValidationError(
            translated_message="errors.storage.runtime.cold_bootstrap_explicit_database_refused",
        )
    if route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE or (
        settings is None and resolve_active_bucket_id() is not None
    ):
        raise StorageValidationError(
            translated_message="errors.storage.runtime.cold_bootstrap_active_profile_refused",
        )
    from .sql.engine import get_engine

    return SecureObjectRepository(engine=get_engine(source), namespace_registry=STORAGE_NAMESPACE_REGISTRY)


@contextmanager
def secure_object_repository_for_staged_bucket(
    bucket_id: str,
    *,
    database_file: Path,
) -> Iterator[SecureObjectRepository]:
    """Yield a repository for a bucket's database BEFORE its capsule is published.

    The one route the storage runtime cannot serve, and the reason is
    structural rather than an oversight.
    :meth:`~adapters.persistence.storage.StorageRuntime.secure_object_repository`
    rebuilds its settings from a storage root plus an active profile, so it
    always resolves the FINAL ``buckets/<bucket_id>/`` path; and capsule
    creation writes revision one into a staging directory that becomes that
    bucket only at the publishing rename. The cold-bootstrap factory is no
    substitute either -- it refuses an explicit database route by design,
    because its own job is the no-pointer-yet case rather than this one.

    So the staging database is addressed explicitly. What stays runtime-owned
    is everything that made a direct construction worth forbidding: the
    namespace registry, the session-bucket binding, the secure-session
    requirement, and the engine's lifetime. A caller receives an open
    repository and cannot leak the engine behind it.

    The caller still owns binding the DEK that opens these rows: the staged
    capsule's key exists only in the creating transaction, which is precisely
    why no ambient session serves this bucket yet.

    Args:
        bucket_id: The profile UUID the staged rows will belong to. Bound as
            the repository's session bucket, so a session serving a different
            profile refuses rather than writing across capsules.
        database_file: The staging database's path. Directory creation is left
            to the engine deliberately: it refuses to bring a bucket root into
            existence -- a bucket exists only once its capsule is published --
            and creates the parents only after that check. Creating them here
            first would satisfy the guard by making its subject exist, which is
            exactly the second bucket creator the refusal is written against.

    Yields:
        A :class:`SecureObjectRepository` open on the staged database.
    """
    from .sql.engine import create_engine_from_settings

    engine = create_engine_from_settings(Settings(cadrumo_database_url=f"sqlite:///{database_file.as_posix()}"))
    try:
        yield SecureObjectRepository(
            engine=engine,
            namespace_registry=STORAGE_NAMESPACE_REGISTRY,
            active_session_bucket_id=bucket_id,
            require_secure_active_session=True,
        )
    finally:
        engine.dispose()


__all__ = [
    "secure_object_repository_for_active_bucket",
    "secure_object_repository_for_active_bucket_or_default_route",
    "secure_object_repository_for_bucket",
    "secure_object_repository_for_cold_bootstrap_state",
    "secure_object_repository_for_staged_bucket",
]
