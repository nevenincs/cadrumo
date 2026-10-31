"""Keep tests out of the account's transport directory, and clear what a hosted runtime left in it."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path

from cadrumo.core.darwin_transport import darwin_socket_directory

from ..posix import posix_storage_identity

_SEARCH_DEPTH = 3


def account_transport_entries() -> frozenset[str]:
    """Name every entry now in the account's transport directory; empty where it is absent."""
    if sys.platform != "darwin":
        return frozenset()
    directory = darwin_socket_directory()
    return frozenset(entry.name for entry in directory.iterdir()) if directory.is_dir() else frozenset()


def _directories(root: Path, depth: int) -> Iterator[Path]:
    yield root
    if depth:
        for child in sorted(root.iterdir()) if root.is_dir() else ():
            if child.is_dir() and not child.is_symlink():
                yield from _directories(child, depth - 1)


def release_hosted_runtime_endpoints(scratch: Path) -> None:
    """Remove the lock and socket a runtime process left for a storage root beneath ``scratch``.

    A runtime process started with a test's storage root resolves the account's transport
    directory, and no caller can redirect it. Its entries are named by that root's physical
    identity, which no other root shares, so removing them once the process has ended
    touches nothing an installed runtime owns.
    """
    if sys.platform != "darwin" or not scratch.is_dir():
        return
    directory = darwin_socket_directory()
    if not directory.is_dir():
        return
    for candidate in _directories(scratch, _SEARCH_DEPTH):
        with suppress(Exception):
            name = posix_storage_identity(candidate)[:32]
            for suffix in (".lock", ".sock"):
                (directory / f"{name}{suffix}").unlink(missing_ok=True)
