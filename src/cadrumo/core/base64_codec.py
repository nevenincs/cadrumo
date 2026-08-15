"""Strict base64 codec for persisted byte fields.

The one home for the ASCII base64 round-trip this project persists byte
material through. Decoding is strict: ``validate=True`` refuses any character
outside the base64 alphabet rather than silently discarding it, so a corrupted
or hand-edited record fails at the boundary instead of yielding shorter bytes
that still parse.

Lives in :mod:`core` because its callers sit in two packages that must not
import each other — the shared-master key surface and the per-profile custody
surface — and a primitive shared by both belongs beneath both rather than in
either. Duplicating a two-line wrapper to avoid that dependency would put the
same encoding decision in two places, where only one of them would be fixed.
"""

from __future__ import annotations

import base64

__all__ = ["b64_decode", "b64_encode"]


def b64_encode(data: bytes) -> str:
    """Return ``data`` as an ASCII base64 string."""
    return base64.b64encode(data).decode("ascii")


def b64_decode(text: str) -> bytes:
    """Return the bytes of a strict ASCII base64 string.

    Raises:
        binascii.Error: When ``text`` carries any character outside the base64
            alphabet, or is not correctly padded.
    """
    return base64.b64decode(text.encode("ascii"), validate=True)
