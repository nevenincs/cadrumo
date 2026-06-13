"""Runtime-backed repository helpers for modelo persistence.

Provides factory helpers that return a :class:`SecureObjectRepository`
bound to the active profile bucket for use by modelo repository classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core import resolve_repository_bucket_id
from ._errors import ModeloError

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ...adapters.persistence.storage import SecureObjectRepository


def resolve_modelo_repository_bucket_id(bucket_id: str | None, *, error_type: type[ModeloError]) -> str:
    """Return an explicit or active profile bucket id for modelo repositories."""
    return resolve_repository_bucket_id(bucket_id, error_type=error_type)


def secure_objects_for_modelo_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return runtime-created secure-object storage for ``bucket_id``.

    Returns:
        A :class:`SecureObjectRepository` scoped to the given modelo bucket.
    """
    from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id)


__all__ = [
    "resolve_modelo_repository_bucket_id",
    "secure_objects_for_modelo_bucket",
]
