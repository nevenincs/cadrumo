"""Announce a waiting profile unlock to background KDF work in any process of the installation.

The KDF permit is one OS file lease per installation root and is not fair, so a
background calibration that kept sampling could keep a person's sign-in waiting.
A waiting unlock therefore leaves a marker beside the lease, named for its
process, while it waits; background work looks for a live marker before each
sample and yields. A marker whose process has died is stale and ignored, so a
crashed waiter never holds background work off for good. The markers carry no
secret and no profile identity.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Final

from .....core.pid_liveness import pid_is_alive

_WAITERS_DIRECTORY: Final = "profile-kdf-waiters"


@contextmanager
def announced_kdf_waiter(lease_root: Path) -> Generator[None]:
    """Mark this process as waiting for the KDF permit until the block ends.

    A marker that cannot be written leaves the wait unannounced rather than
    refusing the unlock: background work then merely fails to yield, which costs
    the person at most one calibration sample.
    """
    marker = lease_root / _WAITERS_DIRECTORY / f"{os.getpid()}-{secrets.token_hex(8)}"
    try:
        marker.parent.mkdir(exist_ok=True)
        marker.touch(exist_ok=False)
    except OSError:
        yield
        return
    try:
        yield
    finally:
        with suppress(OSError):
            marker.unlink(missing_ok=True)


def kdf_waiter_present(lease_root: Path) -> bool:
    """Return whether a live process is waiting for the KDF permit, removing stale markers."""
    directory = lease_root / _WAITERS_DIRECTORY
    try:
        markers = tuple(directory.iterdir())
    except OSError:
        return False
    present = False
    for marker in markers:
        pid_text, _, _token = marker.name.partition("-")
        if pid_text.isdecimal() and pid_is_alive(int(pid_text)):
            present = True
            continue
        with suppress(OSError):
            marker.unlink(missing_ok=True)
    return present


__all__ = ["announced_kdf_waiter", "kdf_waiter_present"]
