"""Atomic IO for the ``<aeat-root>/active-profile`` pointer file.

The pointer file is the third rung of the active-profile precedence
chain (``--profile`` flag > ``AEAT_ACTIVE_PROFILE`` env > pointer file).
The write path uses the write-then-rename pattern so a crashed switch
never produces a truncated pointer; the read path returns ``None``
when the pointer is absent and the higher-level precedence resolver
handles the missing case.
"""

from __future__ import annotations

import os
from pathlib import Path

from ._bucket_pointer import BucketPointer

_POINTER_FILENAME = "active-profile"


def pointer_path(root: Path) -> Path:
    """Return the canonical pointer-file path under the AEAT root."""

    return root / _POINTER_FILENAME


def read_pointer(root: Path) -> BucketPointer | None:
    """Read and strict-validate the pointer file.

    Returns:
        The parsed :class:`BucketPointer`, or ``None`` when the pointer
        file is absent. The higher-level resolver (P04) treats ``None``
        as "fall through to the next precedence rung".

    Raises:
        pydantic.ValidationError: If the pointer file carries an unknown
            key, a wrong type, or a malformed payload.
        tomllib.TOMLDecodeError: If the TOML is unparsable.
    """

    target = pointer_path(root)
    if not target.is_file():
        return None
    text = target.read_text(encoding="utf-8")
    return BucketPointer.from_toml(text)


def write_pointer(root: Path, pointer: BucketPointer) -> None:
    """Atomically write the pointer file via write-then-rename.

    The payload is staged at a ``.tmp`` sibling and renamed via
    :func:`os.replace`; a crashed process therefore leaves either the
    previous good pointer or the new good pointer on disk, never a torn
    intermediate. The AEAT root is created lazily if absent.
    """

    target = pointer_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(pointer.to_toml(), encoding="utf-8")
    os.replace(tmp, target)


__all__ = ["pointer_path", "read_pointer", "write_pointer"]
