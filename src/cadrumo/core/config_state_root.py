"""Application-data anchor and injectable state-root resolution.

Every resolver entry point applies the storage root declaration in
:mod:`core.storage_environment`: a checkout anchors at the checkout, an
installed package anchors at the per-user default root, and neither reads the
process working directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import BaseModel

from .errors.hierarchy import CoreError
from .models import STRICT_FROZEN_CONFIG
from .storage_environment import (
    StorageMode,
    StorageModeEvidence,
    configured_storage_root,
    host_installed_default_root,
    storage_mode,
)
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
    """Frozen inputs for state-root resolution.

    ``repository_root`` names a checkout and selects development mode.
    ``mode`` selects a mode explicitly; when both are absent the mode of the
    running package tree applies.
    """

    model_config = STRICT_FROZEN_CONFIG

    platform: str
    environ: dict[str, str]
    home: Path
    repository_root: Path | None = None
    mode: StorageMode | None = None


def live_state_root_inputs() -> StateRootInputs:
    """Capture the running process's state-root inputs.

    Snapshots :data:`~sys.platform`, a copy of ``os.environ``, and the
    user's home directory into a frozen :class:`StateRootInputs` for
    :func:`platform_user_data_root`.
    """
    return StateRootInputs(
        platform=sys.platform,
        environ=dict(os.environ),
        home=Path.home(),
        repository_root=storage_mode().checkout,
    )


def _mode_evidence(inputs: StateRootInputs) -> StorageModeEvidence:
    if inputs.repository_root is not None:
        if inputs.mode is StorageMode.INSTALLED:
            raise ValueError("an installed state root has no repository root")
        return StorageModeEvidence(StorageMode.DEVELOPMENT, inputs.repository_root)
    detected = storage_mode()
    if inputs.mode is None or inputs.mode is detected.mode:
        return detected
    if inputs.mode is StorageMode.DEVELOPMENT:
        raise ValueError("a development state root needs its repository root")
    return StorageModeEvidence(StorageMode.INSTALLED, None)


def platform_user_data_root(inputs: StateRootInputs) -> Path:
    """Return the anchor for relative paths: the checkout, or the installed default root."""
    evidence = _mode_evidence(inputs)
    if evidence.checkout is not None:
        return evidence.checkout.resolve()
    return host_installed_default_root(inputs.environ, sys_platform=inputs.platform)


def default_storage_root() -> Path:
    """Return the canonical environment-controlled storage default for Settings."""
    return configured_storage_root()
