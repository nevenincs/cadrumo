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

STORAGE_ROOT_MODE: Final[int] = 0o700
"""Permission mode :func:`ensure_storage_tree` requests on the state root."""


def ensure_storage_tree(settings: Settings | None = None) -> Path:
    """Materialize the declared state directories and harden their root.

    This is the sole opt-in topology materialization boundary.  Settings and
    derived-path reads never enter it implicitly.
    """
    from .storage_taxonomy import storage_tree_targets

    resolved = settings if settings is not None else load_settings()
    root = Path(resolved.cadrumo_local_storage_root)

    for target in (root, *storage_tree_targets(resolved)):
        try:
            mode = target.stat().st_mode
        except OSError:
            mode = None
        if mode is not None:
            if not S_ISDIR(mode):
                raise CoreValidationError(
                    translated_message="errors.integrity.integrity_cadrumo_core_validation",
                    context={
                        "state_directory_target": str(target),
                        "occupied_by_file": True,
                        "directory_created": False,
                    },
                )
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
