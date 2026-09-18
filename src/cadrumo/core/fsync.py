"""Settings-free filesystem durability primitives.

This module must remain safe to import while :mod:`cadrumo.core.config` is
still constructing settings. Pointer bootstrap and atomic writes both need
parent-directory durability without importing the lock subsystem, which
depends on runtime settings.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

#: Flags for opening a directory read-only, or ``None`` where the platform has
#: no such contract. Resolved through a module-level ``sys.platform == "win32"``
#: block rather than ``hasattr(os, "O_DIRECTORY")``: the attribute probe is
#: invisible to every checker this project runs, which then report the flag
#: unresolved whenever the tree is analysed for Windows, and the positive block
#: is the only guard shape all of them narrow on.
_directory_open_flags: int | None
if sys.platform == "win32":
    # Windows exposes no directory FlushFileBuffers contract, and therefore no
    # O_DIRECTORY: durability for a directory entry is the caller's rename fence.
    _directory_open_flags = None
else:
    _directory_open_flags = os.O_DIRECTORY | os.O_RDONLY


def fsync_parent_dir(target: Path) -> None:
    """Best-effort fsync of the directory containing ``target``.

    A no-op on a platform that cannot open a directory for flushing.
    """
    if _directory_open_flags is None:
        return
    parent = target.parent
    try:
        fd = os.open(parent, _directory_open_flags)
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
