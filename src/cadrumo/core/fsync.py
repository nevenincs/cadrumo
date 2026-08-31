"""Settings-free filesystem durability primitives.

This module must remain safe to import while :mod:`cadrumo.core.config` is
still constructing settings. Pointer bootstrap and atomic writes both need
parent-directory durability without importing the lock subsystem, which
depends on runtime settings.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_log = logging.getLogger(__name__)


def fsync_parent_dir(target: Path) -> None:
    """Best-effort fsync of the directory containing ``target``."""
    if not hasattr(os, "O_DIRECTORY"):
        return
    parent = target.parent
    try:
        fd = os.open(parent, os.O_DIRECTORY | os.O_RDONLY)
    except OSError:
        _log.debug("fsync_parent_dir: could not open parent directory %s", parent, exc_info=True)
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            _log.debug("fsync_parent_dir: could not fsync parent directory %s", parent, exc_info=True)
    finally:
        try:
            os.close(fd)
        except OSError:
            _log.debug("fsync_parent_dir: could not close parent directory fd for %s", parent, exc_info=True)


__all__ = ["fsync_parent_dir"]
