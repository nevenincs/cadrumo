#!/usr/bin/env python
"""Run a command, staying silent on success and speaking only on failure.

A general signal primitive for the build harness: green/passing tools must
not report anything, so their normal "Success!" / "N files already
formatted" chatter is suppressed when the command exits 0. On a non-zero
exit the captured stdout and stderr are replayed verbatim so the failure is
fully actionable, and the original exit code is propagated.

Usage::

    python -m dev.quality.quiet <command> [args...]

The command runs inside the active environment, so venv console scripts
(``ruff``, ``deptry``, ``lint-imports``) are invoked by bare name.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Final, TextIO

from .._paths import UTF_8

_UTF_8: Final[str] = UTF_8


def main() -> int:
    """Run argv[1:] as a command; echo output only on non-zero exit."""
    command = sys.argv[1:]
    if not command:
        sys.stderr.write("quiet_ok.py: no command given\n")
        return 2

    # Decode explicitly: `text=True` alone uses the locale preferred encoding,
    # which on a Windows console is cp1252. Ruff and lint-imports emit UTF-8
    # (box drawing, arrows, accented source excerpts), so the reader thread
    # died on the first non-cp1252 byte, left stdout as None, and turned a
    # clean gate into a bogus failure.
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        # Mirror of the decode note above: a cp1252 console cannot encode the
        # tool's UTF-8 replay either, so the replay itself raised instead of
        # showing the failure it was invoked to surface.
        _write_replay(sys.stdout, result.stdout)
        _write_replay(sys.stderr, result.stderr)
    return result.returncode


def _write_replay(stream: TextIO, text: str | None) -> None:
    """Replay captured tool output without tripping a narrow console encoding."""
    if not text:
        return
    encoding = stream.encoding or ""
    if encoding.lower().replace("-", "") != "utf8":
        stream.buffer.write(text.encode("utf-8", "replace"))
        stream.flush()
        return
    stream.write(text)


if __name__ == "__main__":
    sys.exit(main())
