"""Decide whether a file descriptor was closed, by the file it names rather than its number.

A closed descriptor number is free for reuse, and POSIX hands out the lowest
free number to the next ``open``. A command that closes a secret-bearing
descriptor and then opens its database, lock or log reuses that number at
once, so ``os.fstat(number)`` succeeds and a bare "fstat raises" check reports
the secret channel as still open when it was closed.

The identity is the open file the number referred to when it was handed over.
The channel is closed when the number no longer resolves, or resolves to a
different file. A command that leaves the channel open keeps the identity, so
the check still fails for the defect it guards.
"""

from __future__ import annotations

import os
import stat

type DescriptorIdentity = tuple[int, int, int]


def descriptor_identity(descriptor: int) -> DescriptorIdentity:
    """Return the file type, device and inode ``descriptor`` currently names."""
    observed = os.fstat(descriptor)
    return (stat.S_IFMT(observed.st_mode), observed.st_dev, observed.st_ino)


def descriptor_was_closed(descriptor: int, identity: DescriptorIdentity) -> bool:
    """Return whether ``descriptor`` no longer names the file captured as ``identity``."""
    try:
        return descriptor_identity(descriptor) != identity
    except OSError:
        return True


__all__ = ["DescriptorIdentity", "descriptor_identity", "descriptor_was_closed"]
