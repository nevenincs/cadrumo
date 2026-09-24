"""Explicit filesystem materialization for the configured storage topology.

Reading :mod:`cadrumo.core.config` is intentionally non-mutating.  Callers that
need the on-disk topology opt into it through this module instead.
"""

from __future__ import annotations

from pathlib import Path
from stat import S_ISDIR
from typing import Final

from .config import Settings, load_settings
from .errors.hierarchy import CoreValidationError
from .storage_taxonomy import StorageGrouping

STORAGE_ROOT_MODE: Final[int] = 0o700
"""Permission mode :func:`ensure_storage_tree` requests on the state root."""


def ensure_storage_tree(
    settings: Settings | None = None,
    *,
    derived_groupings: frozenset[StorageGrouping] | None = None,
) -> Path:
    """Validate explicit storage dependencies and materialize owned defaults.

    This is the sole opt-in topology materialization boundary.  Settings and
    derived-path reads never enter it implicitly. Operator-selected directory
    overrides must already exist; the application-owned root and derived
    defaults are provisioned idempotently. ``derived_groupings`` narrows which
    defaults are provisioned; every explicit dependency is still validated.
    """
    from .storage_taxonomy_locations import storage_tree_targets

    resolved = settings if settings is not None else load_settings()
    root = Path(resolved.cadrumo_local_storage_root)
    explicit_targets = storage_tree_targets(resolved, include_derived=False)
    derived_targets = storage_tree_targets(resolved, include_explicit=False, derived_groupings=derived_groupings)

    for target in explicit_targets:
        _require_directory(target, explicit_override=True)

    for target in (root, *derived_targets):
        if _require_directory(target, explicit_override=False):
            continue
        try:
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


def _require_directory(target: Path, *, explicit_override: bool) -> bool:
    """Return whether ``target`` is a directory, refusing invalid dependencies."""
    try:
        mode = target.stat().st_mode
    except FileNotFoundError:
        if explicit_override:
            raise CoreValidationError(
                translated_message="errors.integrity.integrity_cadrumo_core_validation",
                context={
                    "state_directory_target": str(target),
                    "occupied_by_file": False,
                    "directory_created": False,
                    "explicit_override": True,
                },
            ) from None
        return False
    except OSError as exc:
        context: dict[str, str | bool] = {
            "state_directory_target": str(target),
            "occupied_by_file": False,
            "directory_created": False,
            "stat_error_type": type(exc).__name__,
        }
        if explicit_override:
            context["explicit_override"] = True
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context=context,
        ) from exc

    if not S_ISDIR(mode):
        context = {
            "state_directory_target": str(target),
            "occupied_by_file": True,
            "directory_created": False,
        }
        if explicit_override:
            context["explicit_override"] = True
        raise CoreValidationError(
            translated_message="errors.integrity.integrity_cadrumo_core_validation",
            context=context,
        )
    return True
