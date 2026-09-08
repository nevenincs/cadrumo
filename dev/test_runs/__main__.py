"""The ``python -m dev.test_runs`` entry point.

Usage::

    python -m dev.test_runs lanes <lane> [<lane> ...]

Runs the named just recipes in order, continuing past a failing lane, and
prints a per-lane timing summary. The lane LIST stays in the justfile, where it
is the declarative statement of what the sweep covers; only the sweeping is
here.
"""

from __future__ import annotations

import argparse

from dev.test_runs.lanes import run_lanes


def main(argv: list[str] | None = None) -> int:
    """Dispatch the lane sweep and return its exit code.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        0 when every lane passed, otherwise 1.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dev.test_runs",
        description="Run the full test-lane sweep sequentially.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    lanes = sub.add_parser("lanes", help="run the named lanes in order")
    lanes.add_argument("lane", nargs="+", help="just recipe names")
    args = parser.parse_args(argv)
    return run_lanes(args.lane)


if __name__ == "__main__":
    raise SystemExit(main())
