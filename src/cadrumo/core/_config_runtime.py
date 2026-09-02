"""Private runtime observations supporting the public configuration owner."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any


def active_profile_pointer_observation(
    *,
    normalizer: Callable[[Path | None], Path | None],
    storage_root: Callable[[], Path],
) -> tuple[Path, Any]:
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

    The root is read straight from the environment: that read is deliberately
    independent of the settings model it guards, because it has to answer
    "which pointer would the next construction see" BEFORE any settings exist
    to ask.
    """
    configured_root = os.environ.get("CADRUMO_LOCAL_STORAGE_ROOT")
    root = normalizer(Path(configured_root)) if configured_root else storage_root()
    if root is None:
        raise ValueError(
            "CADRUMO_LOCAL_STORAGE_ROOT is set but normalises to no path, "
            "so the active-profile pointer has no coordinate to be read from",
        )
    from .bucket_pointer import read_pointer

    return (root, read_pointer(root))
