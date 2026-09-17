"""The ``python -m dev.test_runs`` lane-transport entry point.

Usage::

    python -m dev.test_runs lanes <lane> [<lane> ...]

Runs the named just recipes in order, continuing past a failing lane, and
prints a per-lane timing summary. The caller owns the lane list; this module
only supplies execution transport and reporting.
"""

from __future__ import annotations

from .lanes import lane_command_parser, run_lanes


def main(argv: list[str] | None = None) -> int:
    """Dispatch the lane sweep and return its exit code.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        0 when every lane passed, otherwise 1.
    """
    parser = lane_command_parser()
    args = parser.parse_args(argv)
    lane_kinds: dict[str, str] = {}
    for declaration in args.lane_kind:
        lane, separator, kind = declaration.partition("=")
        if not separator or not lane or not kind:
            parser.error(f"invalid --lane-kind {declaration!r}; expected LANE=KIND")
        if lane in lane_kinds:
            parser.error(f"lane kind declared more than once for {lane!r}")
        lane_kinds[lane] = kind
    return run_lanes(
        args.lane,
        json_events=args.json_events,
        persist_evidence=not args.no_evidence,
        preflight_count=args.preflight_count,
        lane_kinds=lane_kinds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
