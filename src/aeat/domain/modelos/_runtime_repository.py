"""Runtime-backed repository helpers for modelo persistence."""

from __future__ import annotations

from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...core._bucket_pointer_io import resolve_active_bucket_id
from ...core.i18n import tr
from ._errors import ModeloError


def resolve_modelo_repository_bucket_id(bucket_id: str | None, *, error_type: type[ModeloError]) -> str:
    """Return an explicit or active profile bucket id for modelo repositories."""

    if bucket_id is not None:
        trimmed = bucket_id.strip()
        if trimmed:
            return trimmed
        raise error_type(tr("application.workflow.errors.no_active_profile_bucket"))
    active = resolve_active_bucket_id()
    if active is None:
        raise error_type(tr("application.workflow.errors.no_active_profile_bucket"))
    return active


def secure_objects_for_modelo_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``."""

    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "resolve_modelo_repository_bucket_id",
    "secure_objects_for_modelo_bucket",
]
