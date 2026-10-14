"""Child side of the contained standard-pipe launch: read one frame, answer, await close.

Given the argument ``stderr``, the child first writes one diagnostic line to standard error.
"""

from __future__ import annotations

import hashlib
import sys


def main() -> None:
    """Answer one standard-input line with its digest, then exit when standard input closes."""
    if sys.argv[1:] == ["stderr"]:
        sys.stderr.buffer.write(b"the child's diagnostic\n")
        sys.stderr.buffer.flush()
    frame = sys.stdin.buffer.readline()
    sys.stdout.buffer.write(hashlib.sha256(frame).hexdigest().encode("ascii") + b"\n")
    sys.stdout.buffer.flush()
    remainder = sys.stdin.buffer.read()
    sys.exit(0 if remainder == b"" else 3)


if __name__ == "__main__":
    main()
