"""Refuse a built distribution the index would reject on size.

The publish path builds with ``uv build`` into a plain directory rather than
through the cohort builder, and it runs before any development dependency is
installed. It therefore needs a check that reaches the same limit as every
other consumer while importing nothing beyond the standard library: a workflow
step that inlined the number would be exactly the drifting copy
:mod:`dev.packaging._distribution_limits` exists to prevent, and one that
imported the cohort builder would fail on its unresolved third-party imports.

The cap is inclusive. PyPI rejects a file *at* the limit as well as over it, so
a distribution that lands exactly on the boundary is refused here rather than
at upload, after the reversible destinations have already been written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from ._distribution_limits import PYPI_FILE_CAP_BYTES

__all__ = ["built_distributions", "main", "oversize_distributions"]

#: What an index accepts as a distribution. ``uv build`` also drops a
#: ``.gitignore`` into its output directory, and a check that measured every
#: file would report that marker as a distribution it had cleared.
_DISTRIBUTION_SUFFIXES: Final = (".whl", ".tar.gz")


def built_distributions(directory: Path) -> list[Path]:
    """Return every uploadable distribution in ``directory``."""
    return sorted(
        entry for entry in directory.iterdir() if entry.is_file() and entry.name.endswith(_DISTRIBUTION_SUFFIXES)
    )


def oversize_distributions(directory: Path) -> list[Path]:
    """Return every distribution in ``directory`` at or over the index cap."""
    return [entry for entry in built_distributions(directory) if entry.stat().st_size >= PYPI_FILE_CAP_BYTES]


def main() -> int:
    """Report every built distribution and refuse the ones over the cap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    directory = parser.parse_args().directory
    if not directory.is_dir():
        print(f"no such directory: {directory}", file=sys.stderr)
        return 1
    files = built_distributions(directory)
    if not files:
        print(f"no distributions found under {directory}", file=sys.stderr)
        return 1
    over = oversize_distributions(directory)
    for entry in over:
        print(
            f"{entry.name} is {entry.stat().st_size} bytes, at or over the {PYPI_FILE_CAP_BYTES} byte index cap",
            file=sys.stderr,
        )
    for entry in files:
        print(f"{entry.name} {entry.stat().st_size}")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
