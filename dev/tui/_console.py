"""UTF-8 console output for the visual review commands."""

from __future__ import annotations

import sys

from dev._paths import UTF_8


def _echo(text: str) -> None:
    """Write a line as UTF-8 whatever the console code page claims.

    Written as bytes rather than through ``print``: a Windows console defaults
    to cp1252, which mangles the box-drawing and dash characters the harness's
    own diagnostics are built from -- the same reason the development harness
    encodes its output by hand.
    """
    sys.stdout.buffer.write(text.encode(UTF_8, errors="replace") + b"\n")
    sys.stdout.buffer.flush()
