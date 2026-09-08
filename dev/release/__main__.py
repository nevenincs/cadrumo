"""The ``python -m dev.release`` entry point.

Usage::

    python -m dev.release preview
    python -m dev.release rollback <version>

Both actions are read-only with respect to the published release: `preview` is
a release-please dry run, and `rollback` prints a human-run procedure.
"""

from __future__ import annotations

import argparse

from dev.release.preview import preview
from dev.release.rollback import print_procedure


def main(argv: list[str] | None = None) -> int:
    """Dispatch one release action and return its exit code.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The exit code of the selected action.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.release",
        description="Preview a release, or print a rollback procedure.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preview", help="release-please dry run; mutates nothing")
    rollback = sub.add_parser("rollback", help="print the rollback procedure")
    rollback.add_argument("version", help="the released version being pulled")
    args = parser.parse_args(argv)

    if args.action == "preview":
        return preview()
    return print_procedure(args.version)


if __name__ == "__main__":
    raise SystemExit(main())
