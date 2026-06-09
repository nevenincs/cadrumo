#!/usr/bin/env python
"""Reduce jscpd console output to signal only.

jscpd prints ANSI-coloured clone blocks followed by a summary box-table and
a timing line. Reading from stdin, this filter strips the ANSI escapes,
keeps only the actionable clone blocks (capped, worst volume not sorted by
jscpd so insertion order is preserved), and collapses the box-table to a
single aggregate line. On a clean run it prints one green aggregate line.

Always exits 0 — duplication is advisory debt, not a gate.
"""

from __future__ import annotations

import re
import sys

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_FOUND = re.compile(r"Found (\d+) clones?")
_TABLE_PCT = re.compile(r"\((\d+(?:\.\d+)?)%\)")
_CLONE_CAP = 20


def main() -> int:
    """Filter jscpd stdout to clone blocks plus a one-line aggregate."""
    raw = _ANSI.sub("", sys.stdin.read())
    lines = raw.splitlines()

    blocks: list[list[str]] = []
    current: list[str] = []
    total = 0
    duplicated_pct = ""

    for line in lines:
        if line.startswith("Clone found"):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current:
            if line.strip():
                current.append(line.replace("\\", "/").rstrip())
            else:
                blocks.append(current)
                current = []
            continue
        found = _FOUND.search(line)
        if found:
            total = int(found.group(1))
        if "Duplicated lines" not in line and "%" in line and not duplicated_pct:
            pct = _TABLE_PCT.search(line)
            if pct:
                duplicated_pct = pct.group(1)
    if current:
        blocks.append(current)

    if not blocks:
        print("duplication: no clones found.")
        return 0

    pct_clause = f", {duplicated_pct}% duplicated lines" if duplicated_pct else ""
    print(f"duplication: {total or len(blocks)} clones{pct_clause}.")
    for block in blocks[:_CLONE_CAP]:
        print()
        print("\n".join(block))
    if len(blocks) > _CLONE_CAP:
        print(f"\n... {len(blocks) - _CLONE_CAP} more clones")
    return 0


if __name__ == "__main__":
    sys.exit(main())
