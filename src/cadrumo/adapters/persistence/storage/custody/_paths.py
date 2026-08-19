"""Taxonomy-backed paths for one immutable profile capsule."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final
from uuid import UUID

from .....core import StorageCategory, bucket_scoped_storage_path, storage_location
from .....core.identity import canonical_profile_bucket_id
from .._path_safety import safe_repository_id
from ..errors import PathContainmentError

if TYPE_CHECKING:
    from .....core.config import Settings

_PROFILE_ID_PATH_CONTEXT: Final = "profile_id"


_PROFILE_CUSTODY_CATEGORIES: Final[frozenset[StorageCategory]] = frozenset(
    {
        StorageCategory.PROFILE_CAPSULE_CUSTODY,
        StorageCategory.PROFILE_CAPSULE_PASSWORD_ENVELOPE,
        StorageCategory.PROFILE_CAPSULE_RECOVERY_ENVELOPE,
        StorageCategory.PROFILE_CAPSULE_DATA,
        StorageCategory.PROFILE_CAPSULE_COMMIT,
    },
)


def profile_custody_directory_name(profile_id: object) -> str:
    """Return the sole directory name a capsule for ``profile_id`` may occupy.

    This is where a profile identity becomes a filesystem name, so the value is
    treated as untrusted here regardless of what the calling signature claims --
    the same posture :func:`~._zeroise.zeroise` takes at the wipe boundary, and
    for the same reason: the damage of an unchecked value is silent. A bucket
    identity is a plain string in much of the system and its accepted set
    includes system-scoped sentinels that are not profile UUIDs at all, so a
    value of the wrong type arriving here would compose a directory beside real
    capsules -- or, for a relative-path token, one outside the buckets root
    entirely.

    Shape rejection reuses the substrate's :func:`safe_repository_id` rather
    than restating separator and dot-token rules locally, so this boundary
    cannot drift from every other identifier-to-filename boundary.

    Args:
        profile_id: Must be a :class:`~uuid.UUID`. Any other value, including a
            string that merely parses as one, is rejected at runtime.

    Returns:
        The canonical directory name, which is exactly the name the anchored
        capsule discoverer recognises.

    Raises:
        PathContainmentError: When ``profile_id`` is not a :class:`~uuid.UUID`,
            when it is a UUID of a version the profile aggregate never mints,
            or when its canonical rendering would not compose into a safe
            single directory name.
    """
    if not isinstance(profile_id, UUID):
        raise PathContainmentError(
            "profile custody path requires a UUID profile identifier",
            context={
                "path_context": _PROFILE_ID_PATH_CONTEXT,
                "violation": "profile_id_not_uuid",
            },
        )
    try:
        canonical = canonical_profile_bucket_id(profile_id)
    except ValueError as exc:
        raise PathContainmentError(
            "profile custody path requires a canonical profile identity",
            context={
                "path_context": _PROFILE_ID_PATH_CONTEXT,
                "violation": "profile_id_not_canonical_identity",
            },
        ) from exc
    return safe_repository_id(canonical, context=_PROFILE_ID_PATH_CONTEXT)


def profile_custody_path(
    profile_id: UUID,
    category: StorageCategory,
    *,
    settings: Settings | None = None,
    root: Path | None = None,
) -> Path:
    """Resolve one current-format custody artifact beneath ``profile_id``."""
    if category not in _PROFILE_CUSTODY_CATEGORIES:
        raise ValueError(f"storage category {category.value!r} is not a profile-custody artifact")
    directory_name = profile_custody_directory_name(profile_id)
    if root is not None:
        if settings is not None:
            raise ValueError("profile custody path accepts either settings or root, never both")
        bucket_root = Path(root) / storage_location(StorageCategory.BUCKETS).relative_path()
        return bucket_root / directory_name / storage_location(category).relative_path()
    return bucket_scoped_storage_path(category, directory_name, settings=settings)


__all__ = ["profile_custody_directory_name", "profile_custody_path"]
