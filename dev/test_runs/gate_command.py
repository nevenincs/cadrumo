"""The ``gate`` and ``gate-timing`` actions of ``python -m dev.test_runs``."""

from __future__ import annotations

import argparse

from dev.exit_codes import OK
from dev.paths import REPO_ROOT

from .gate_graph import GateGraphError, load_gate_graph
from .gate_runner import graph_identity, run_gate
from .gate_schedule import simulate_schedule
from .gate_timing import GateTimingError, write_timings


def gate_action(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Run, or with ``--dry-run`` print, the gate graph the arguments name."""
    try:
        graph = load_gate_graph(args.graph).select(tuple(args.only))
        graph.check_budget(args.budget)
    except (GateGraphError, OSError) as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(f"gate schedule, budget {args.budget}, every node taken as one equal step:")
        for index, wave in enumerate(simulate_schedule(graph, args.budget), start=1):
            weight = sum(node.weight for node in wave)
            names = ", ".join(f"{node.name}[{node.kind} w{node.weight}]" for node in wave)
            print(f"  step {index}: weight {weight}/{args.budget}: {names}")
        return OK
    if args.record_dir is None or not args.head_label:
        parser.error("--record-dir and --head-label are required unless --dry-run is given")
    result = run_gate(
        graph,
        budget=args.budget,
        record_dir=args.record_dir,
        head_label=args.head_label,
        tree_root=args.tree_root or REPO_ROOT,
        graph_source=graph_identity(args.graph),
        json_events=args.json_events,
    )
    return result.exit_code


def gate_timing_action(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Write the per-file seconds table of a gate record."""
    try:
        destination = write_timings(args.record_dir, args.output)
    except GateTimingError as exc:
        parser.error(str(exc))
    print(f"test-file seconds: {destination}")
    return OK
