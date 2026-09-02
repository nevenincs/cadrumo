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

from .._paths import UTF_8
from .suite import annotate_unevaluated_contracts

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
    # The decode above fixes OUR side. The child still picks its own stdout
    # encoding, and rich falls back to a legacy Windows console writer that
    # encodes to cp1252 -- lint-imports then died inside its own progress
    # rendering before any contract verdict reached us. Naming the child's
    # stdio encoding keeps the tool's UTF-8 output writable at the source.
    child_env = {**os.environ, "PYTHONIOENCODING": _UTF_8}
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        errors="replace",
        check=False,
        env=child_env,
    )

    if result.returncode != 0:
        # Mirror of the decode note above: a cp1252 console cannot encode the
        # tool's UTF-8 replay either, so the replay itself raised instead of
        # showing the failure it was invoked to surface.
        # import-linter aborts before evaluating ANY contract when one ignore
        # pin matches nothing, and its whole output is then the line naming
        # that pin. Replayed bare, that reads as one narrow complaint; it is
        # every layering contract going unchecked. CI runs this wrapper, so
        # without the annotation here the distinction never reaches the only
        # place that looks. Applied unconditionally rather than keyed on the
        # command: the annotator matches the linter's own markers, so any other
        # tool's failure passes through untouched, and keying on a command name
        # would make this branch unreachable from a test that cannot invoke the
        # real binary.
        _write_replay(sys.stdout, annotate_unevaluated_contracts(result.stdout or ""))
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
