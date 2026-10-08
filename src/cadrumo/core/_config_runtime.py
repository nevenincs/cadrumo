"""Private runtime observations supporting the public configuration owner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bucket_pointer import BucketPointer


def active_profile_pointer_observation(
    *,
    normalizer: Callable[[Path | None], Path | None],
    storage_root: Callable[[], Path],
) -> tuple[Path, BucketPointer]:
    """Identify the current active-profile pointer through its native coordinate.

    Settings construction is not a pure function of the environment: when
    ``cadrumo_database_url`` is unset, the post-validator reads the
    ``active-profile`` pointer file and derives the bucket's database route
    from it. That makes the pointer a construction INPUT, and it moves whenever
    ``config login``/``logout`` writes it — inside a live process, for a
    long-running interactive or external session.

    Holding one settings instance across such a switch would keep serving the
    previous profile's database route, so the canonical durable transition
    coordinate is folded into the cache key. A fresh root observes the initial
    absent coordinate zero; a later clear is a distinct persisted tombstone.

    The root is read straight from the environment through ``storage_root``,
    which applies the storage root declaration's precedence: that read is
    deliberately independent of the settings model it guards, because it has
    to answer "which pointer would the next construction see" BEFORE any
    settings exist to ask.
    """
    root = normalizer(storage_root())
    if root is None:
        raise ValueError("the storage root normalises to no path, so the active-profile pointer has no coordinate")
    from .bucket_pointer import read_pointer_selection

    return (root, read_pointer_selection(root))
