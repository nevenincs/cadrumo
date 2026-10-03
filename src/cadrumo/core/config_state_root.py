"""Repository-backed application-data defaults and injectable state-root resolution.

Every resolver entry point uses the canonical storage environment authority.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel

from .errors.hierarchy import CoreError
from .models import STRICT_FROZEN_CONFIG
from .storage_environment import configured_storage_root, project_root
from .storage_taxonomy import StorageCategory
from .storage_taxonomy_locations import storage_location

#: Bucket container directory name, read from the one core storage authority.
BUCKETS_DIRNAME = storage_location(StorageCategory.BUCKETS).subpath
#: Per-bucket database directory name, read from the one core storage authority.
BUCKET_DB_DIRNAME = storage_location(StorageCategory.BUCKET_DATABASE).subpath
#: Canonical SQLite filename, read from the one core storage authority.
PRODUCT_DATABASE_FILENAME = storage_location(StorageCategory.ROOT_FALLBACK_DATABASE).subpath
#: Retired ``aeat`` database filename inspected only for refusal.
FORMER_PRODUCT_DATABASE_FILENAME = "aeat.db"


class FormerProductStateError(CoreError):
    """Raised when Cadrumo detects a retired ``aeat`` database.

    Detection is refusal-only. The resolver does not open, read, move, re-key,
    delete, or adopt the retired database.
    """


def refuse_former_product_database(storage_root: Path, *, bucket_id: str | None = None) -> None:
    """Refuse a recognizable retired ``aeat`` database without opening it.

    Only filesystem metadata is inspected. The retired database is never
    connected to, read, copied, moved, deleted, or adopted.
    """
    parent = storage_root
    if bucket_id:
        parent = parent / BUCKETS_DIRNAME / bucket_id / BUCKET_DB_DIRNAME
    former_database = parent / FORMER_PRODUCT_DATABASE_FILENAME
    if not former_database.exists():
        return
    raise FormerProductStateError(
        "Cadrumo detected an incompatible retired `aeat` database named "
        f"{FORMER_PRODUCT_DATABASE_FILENAME!r}. Cadrumo will not read, move, "
        "copy, delete, migrate, or adopt that database.",
    )


class StateRootInputs(BaseModel):
    """Frozen inputs for state-root resolution, including the project anchor."""

    model_config = STRICT_FROZEN_CONFIG

    platform: str
    environ: dict[str, str]
    home: Path
    repository_root: Path | None = None


class StateRootResolution(BaseModel):
    """Resolved application-data anchor and default storage root."""

    model_config = STRICT_FROZEN_CONFIG

    platform_user_data_root: Path
    storage_root: Path


def live_state_root_inputs() -> StateRootInputs:
    """Capture the running process's state-root inputs.

    Snapshots :data:`~sys.platform`, a copy of ``os.environ``, and the
    user's home directory into a frozen :class:`StateRootInputs` for
    :func:`resolve_state_root`.
    """
    return StateRootInputs(
        platform=sys.platform,
        environ=dict(os.environ),
        home=Path.home(),
        repository_root=project_root(),
    )


def platform_user_data_root(inputs: StateRootInputs) -> Path:
    """Return the project application-data anchor on every platform."""
    return (inputs.repository_root or project_root()).resolve()


def resolve_state_root(inputs: StateRootInputs) -> StateRootResolution:
    """Resolve all defaults and relative overrides beneath the project anchor."""
    anchor = platform_user_data_root(inputs)
    return StateRootResolution(
        platform_user_data_root=anchor,
        storage_root=configured_storage_root(environ=inputs.environ, repository_root=anchor),
    )


def default_storage_root() -> Path:
    """Return the canonical environment-controlled storage default for Settings."""
    return configured_storage_root()
