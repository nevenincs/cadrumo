"""The environment variable that names one profile's own folder.

Profile selection never comes from the environment: the active-profile pointer
and the in-process override are its only writers (:mod:`core.config`). This
variable runs the other way. A process that already knows which profile it
serves derives that profile's folder, ``<storage root>/buckets/<profile id>``,
and hands it to the children it starts, so that they and the tools they run
find the profile's data without resolving a selection of their own.

Nothing in Cadrumo reads it back to choose a profile, and a value received
from a parent is never relayed: each launcher derives it again from the
profile it is launching for, so a child started after a profile switch names
the new profile's folder and a stale value cannot travel down a process tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from .identity.profile import canonical_profile_bucket_id

if TYPE_CHECKING:
    from uuid import UUID

PROFILE_ROOT_VARIABLE: Final = "CADRUMO_PROFILE_ROOT"
"""The derived, read-only name of the folder of the profile a process serves."""


def profile_root(storage_root: Path, profile_id: str | UUID) -> Path:
    """Return the folder that holds ``profile_id``'s bucket under ``storage_root``.

    Raises:
        ValueError: When ``profile_id`` is not a canonical profile identity, so
            no value can name a folder outside the bucket container.
    """
    from .storage_taxonomy import StorageCategory
    from .storage_taxonomy_locations import storage_location

    container = storage_location(StorageCategory.BUCKETS).relative_path()
    return Path(storage_root) / container / canonical_profile_bucket_id(profile_id)


def profile_root_environment(storage_root: Path, profile_id: str | UUID | None) -> dict[str, str]:
    """Return the variable naming ``profile_id``'s folder, or nothing when no profile is served."""
    if profile_id is None:
        return {}
    return {PROFILE_ROOT_VARIABLE: str(profile_root(storage_root, profile_id))}


__all__ = ["PROFILE_ROOT_VARIABLE", "profile_root", "profile_root_environment"]
