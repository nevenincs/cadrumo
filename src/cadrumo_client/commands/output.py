"""Small presentation primitives shared by command frontends."""

from __future__ import annotations

import contextlib
import io
import sys

from cadrumo.core.redaction.rules import redact_for_cli_output


def write_stderr(text: str, *, stream: io.TextIOBase | None = None) -> None:
    """Write a redacted line with a UTF-8 fallback when the stream supports it."""
    target = sys.stderr if stream is None else stream
    safe = redact_for_cli_output(text)
    reconfigure = getattr(target, "reconfigure", None)
    if callable(reconfigure):
        with contextlib.suppress(Exception):
            reconfigure(encoding="utf-8", errors="strict")
    try:
        target.write(safe + "\n")
        target.flush()
    except UnicodeEncodeError:
        buffer = getattr(target, "buffer", None)
        if buffer is not None:
            buffer.write((safe + "\n").encode("utf-8", errors="replace"))
            buffer.flush()
        else:
            target.write(safe.encode("ascii", errors="replace").decode("ascii") + "\n")
            target.flush()
