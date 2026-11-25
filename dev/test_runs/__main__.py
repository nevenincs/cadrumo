"""The ``python -m dev.test_runs`` lane-transport entry point.

Usage::

    python -m dev.test_runs lanes <lane> [<lane> ...]
    python -m dev.test_runs gate --graph FILE --budget N --record-dir DIR --head-label LABEL
    python -m dev.test_runs gate-timing --record-dir DIR

``lanes`` runs the named just recipes in order, continuing past a failing
lane, and prints a per-lane timing summary. ``gate`` runs a declared node graph
concurrently under one worker budget and writes a durable record;
``gate-timing`` turns that record's JUnit reports into per-file seconds. The
caller owns the lane list and the graph; this module only supplies execution
transport and reporting.
"""

from __future__ import annotations

from .gate_command import gate_action, gate_timing_action
from .lanes import lane_command_parser, run_lanes


def main(argv: list[str] | None = None) -> int:
    """Dispatch the requested action and return its exit code.

    Args:
        argv: The argument vector, or ``None`` to read :data:`sys.argv`.

    Returns:
        The action's exit code; see ``dev/EXIT-CODES.md``.
    """
    parser = lane_command_parser()
    args = parser.parse_args(argv)
    if args.action == "gate":
        return gate_action(parser, args)
    if args.action == "gate-timing":
        return gate_timing_action(parser, args)
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
