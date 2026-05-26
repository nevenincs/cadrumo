"""Runtime-owned secure-object repository factories."""

from __future__ import annotations

from ....core.config import Settings, load_settings
from .errors import StorageValidationError
from .runtime import inspect_bucket_storage_runtime
from .sql import SecureObjectRepository


def secure_object_repository_for_bucket(
    bucket_id: str,
    settings: Settings | None = None,
) -> SecureObjectRepository:
    """Return a bucket-attached secure-object repository through storage runtime."""

    return inspect_bucket_storage_runtime(bucket_id, settings or load_settings()).secure_object_repository()


def secure_object_repository_for_active_bucket() -> SecureObjectRepository:
    """Return a bucket-attached repository for the selected active profile."""

    from ....core._bucket_pointer_io import resolve_active_bucket_id
    from ....core.i18n import tr

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise StorageValidationError(
            tr("application.workflow.errors.no_active_profile_bucket"),
            translated_message="errors.storage.runtime.not_ready",
        )
    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "secure_object_repository_for_active_bucket",
    "secure_object_repository_for_bucket",
]
