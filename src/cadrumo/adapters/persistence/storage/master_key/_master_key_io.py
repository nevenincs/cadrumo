"""Hardened byte writes and buffer zeroisation for the master-key package.

What survives of a module that also owned passphrase resolution. The file
backend that prompted for, or read, an operator passphrase to derive a
process-wide key-encryption key is gone, and its resolver and callback alias
went with it: the passphrase that matters is the profile's, resolved by the
custody package against that profile's own capsule.

``_zeroise`` outlived it because it never belonged to that backend: it is the
buffer wipe a bucket session performs on close.
"""

from __future__ import annotations

__all__ = [
    "_zeroise",
]


def _zeroise(buffer: bytearray | None) -> None:
    """Best-effort overwrite of a mutable buffer with zero bytes."""
    if buffer is None:
        return
    for i in range(len(buffer)):
        buffer[i] = 0
