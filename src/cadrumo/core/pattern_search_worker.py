"""Child-only search of person-supplied patterns, ended from outside when it overruns.

``re`` keeps the interpreter lock for the whole of one search, so a pattern that
backtracks without end stops every thread of the process running it and cannot
be interrupted from within. Such a search therefore runs here, in a fresh
interpreter its supervisor can kill. The import closure stays the standard
library: this starts for each batch.

The conversation is one JSON document on stdin and JSON lines on stdout, never
the command line, because the texts are a taxpayer's movement descriptions.
"""

from __future__ import annotations

import json
import re
import sys
from typing import BinaryIO, Final, cast

PATTERN_FLAGS: Final = re.IGNORECASE
"""How a person-supplied pattern reads a text: anywhere in it, ignoring case."""

PATTERN_COMPILE_FAILURES: Final = (re.error, ValueError, OverflowError, RecursionError, MemoryError)
"""Everything ``re.compile`` raises for a text it cannot read as a pattern."""


def _emit(stream: BinaryIO, **line: object) -> None:
    stream.write(json.dumps(line).encode("ascii") + b"\n")
    stream.flush()


def run(source: BinaryIO, sink: BinaryIO) -> None:
    """Say ready, read the request, and report each pattern as it finishes."""
    _emit(sink, ready=True)
    request = json.loads(source.read())
    texts = cast("list[str]", request["texts"])
    remaining = list(range(len(texts)))
    for index, pattern in enumerate(cast("list[str]", request["patterns"])):
        if not remaining:
            break
        try:
            compiled = re.compile(pattern, PATTERN_FLAGS)
        except PATTERN_COMPILE_FAILURES:
            _emit(sink, unreadable=index)
            return
        hits: list[int] = []
        unmatched: list[int] = []
        try:
            for position in remaining:
                (hits if compiled.search(texts[position]) is not None else unmatched).append(position)
        except MemoryError:
            # Backtracking state outgrew the child's memory limit: the same overrun, seen sooner.
            _emit(sink, exhausted=index)
            return
        _emit(sink, finished=index, hits=hits)
        remaining = unmatched
    _emit(sink, done=True)


if __name__ == "__main__":
    run(sys.stdin.buffer, sys.stdout.buffer)
