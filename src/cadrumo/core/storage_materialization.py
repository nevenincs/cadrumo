"""Explicit filesystem materialization for the configured storage topology.

Reading :mod:`cadrumo.core.config` is intentionally non-mutating.  Callers that
need the on-disk topology opt into it through this module instead.
"""

from __future__ import annotations

from pathlib import Path
from stat import S_ISDIR

from .config import Settings, load_settings
from .errors.hierarchy import CoreValidationError
from .storage_environment import ensure_storage_root
from .storage_taxonomy import StorageGrouping


def ensure_storage_tree(
    settings: Settings | None = None,
    *,
    derived_groupings: frozenset[StorageGrouping] | None = None,
) -> Path:
    """Materialize the storage root and the members it owns, idempotently.

    This is the sole opt-in topology materialization boundary.  Settings and
    path reads never enter it implicitly. ``derived_groupings`` narrows which
    members are provisioned. Runtime-owned members, the connection namespace
    among them, are neither created nor required here: the installed runtime
    creates them itself.
    """
    from .storage_taxonomy_locations import storage_tree_targets

    resolved = settings if settings is not None else load_settings()
    root = Path(resolved.cadrumo_storage_root)
    targets = storage_tree_targets(resolved, derived_groupings=derived_groupings)

    for target in (root, *targets):
        if _require_directory(target):
            continue
        try:
            if target == root:
                ensure_storage_root(target)
            else:
                target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "state_directory_target": str(target),
                    "occupied_by_file": False,
                    "directory_created": False,
                    "mkdir_error_type": type(exc).__name__,
                },
            ) from exc

    from .file_permissions import restrict_directory_permissions

    restrict_directory_permissions(root)
    return root


def _require_directory(target: Path) -> bool:
    """Return whether ``target`` is a directory, refusing a file or unreadable occupant."""
    try:
        mode = target.stat().st_mode
    except (FileNotFoundError, NotADirectoryError):
        # A target below a file cannot exist; POSIX says so with ENOTDIR where
        # Windows reports a missing file, and both are the absent directory.
        return False
    except OSError as exc:
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "state_directory_target": str(target),
                "occupied_by_file": False,
                "directory_created": False,
                "stat_error_type": type(exc).__name__,
            },
        ) from exc

    if not S_ISDIR(mode):
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context={
                "state_directory_target": str(target),
                "occupied_by_file": True,
                "directory_created": False,
            },
        )
    return True
