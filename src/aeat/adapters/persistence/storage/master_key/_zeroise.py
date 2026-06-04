"""In-memory zeroisation primitives for the master-key surface.

The substrate holds the unlocked KEK and DEK in `bytearray` buffers
attached to a `BucketSession` instance. On `lock`
the session calls into this module to overwrite each buffer with zero
bytes before dropping the reference, so a memory-disclosure bug
elsewhere (a debug traceback, a post-mortem core dump) cannot surface
the key bytes.

Honest contract: zeroisation in Python is best-effort. The interpreter
may have produced short-lived `bytes` copies of the buffer during
property reads (`BucketSession.kek` materialises `bytes(self._kek_buffer)`
on each access); the garbage collector owns the lifetime of those
copies and there is no portable Python primitive that can reach them.
The substrate confines KEK / DEK plaintext to `bytearray` containers
and overwrites them at lock so the steady-state in-memory copy is
zeroed; the transient `bytes` view lifetimes are bounded by GC.

A future native-extension wipe (`CRYPTO_cleanse`, `SecureZeroMemory`)
would tighten this guarantee but is out of scope for this module.
"""

from __future__ import annotations

from typing import Final

from ._errors import MasterKeyTypeError

_MASTER_KEY_TYPE_MESSAGE_KEY: Final[str] = "errors.internal.internal_master_key_type"


def _master_key_type_error(buffer: object) -> MasterKeyTypeError:
    return MasterKeyTypeError(
        "zeroise() requires a mutable bytearray buffer",
        context={"received_type": type(buffer).__name__},
        translated_message=_MASTER_KEY_TYPE_MESSAGE_KEY,
    )


def zeroise(buffer: object) -> None:
    """Overwrite every byte of a mutable buffer with zero.

    This is the canonical wipe-primitive consumed by `BucketSession.close()`.
    The function operates in place; the caller's reference still points
    at the same `bytearray` object after the call returns, but every
    byte has been replaced by `0x00`.

    Args:
        buffer: Must be a ``bytearray``. Any other type is rejected at
            runtime with :exc:`TypeError`.

    Raises:
        MasterKeyTypeError: When ``buffer`` is not a ``bytearray``.
    """
    if not isinstance(buffer, bytearray):
        raise _master_key_type_error(buffer)
    for index in range(len(buffer)):
        buffer[index] = 0


__all__ = ["zeroise"]
