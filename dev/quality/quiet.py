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

import os
import subprocess
import sys
from typing import Final, TextIO

from dev._paths import UTF_8

_UTF_8: Final[str] = UTF_8


def main(argv: list[str] | None = None) -> int:
    """Run the given command; echo output only on non-zero exit.

    Takes its arguments so the wrapper can be exercised. It read ``sys.argv``
    directly, which left the one primitive every gate runs through reachable
    only by launching a process.
    """
    command = sys.argv[1:] if argv is None else list(argv)
    if not command:
        sys.stderr.write("quiet: no command given" + chr(10))
        return 2

    # Decode explicitly: `text=True` alone uses the locale preferred encoding,
    # which on a Windows console is cp1252. Ruff and lint-imports emit UTF-8
    # (box drawing, arrows, accented source excerpts), so the reader thread
    # died on the first non-cp1252 byte, left stdout as None, and turned a
    # clean gate into a bogus failure.
    # The decode above fixes OUR side. The child still picks its own stdout
    # encoding, and rich falls back to a legacy Windows console writer that
    # encodes to cp1252 -- lint-imports then died inside its own progress
    # rendering before any contract verdict reached us. Naming the child's
    # stdio encoding keeps the tool's UTF-8 output writable at the source.
    child_env = {**os.environ, "PYTHONIOENCODING": _UTF_8}
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=_UTF_8,
            errors="replace",
            check=False,
            env=child_env,
        )
    except OSError as error:
        # The wrapper every gate runs through. An absent or unrunnable tool
        # raised out of here as a traceback whose last line is a Windows error
        # number, so a mistyped command in a recipe reported neither the tool
        # nor the recipe - in the one output CI keeps.
        sys.stderr.write(f"quiet: cannot run {command[0]!r}: {error}" + chr(10))
        return 127

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
