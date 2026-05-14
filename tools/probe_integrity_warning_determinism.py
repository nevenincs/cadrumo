"""Determinism probe for the secure-objects integrity scan.

Repeats the integrity scan N times without mutation and records the
per-namespace readable / unreadable counts on each pass, the observing
process id, the wall-clock ISO-8601 timestamp, and the pids of any peer
processes that look like aeat writers running concurrently with the
scan.

The output is a JSONL stream on stdout. Each line is one (run,
namespace) observation. The schema is intentionally narrow so
downstream analysis can confirm or falsify the concurrent-writer
hypothesis recorded in
``2026-05-14-cli-workflow-redesign-integrity-warning-stability-adr``.

Usage::

    python tools/probe_integrity_warning_determinism.py --runs 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aeat.application.diagnostics import _probe_secure_objects_integrity  # noqa: E402


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _peer_writer_pids(self_pid: int) -> tuple[int, ...]:
    """Return pids of peer processes that look like aeat writers.

    Returns an empty tuple when ``psutil`` is not installed; the probe
    keeps the dependency optional so it can run in any environment.
    """

    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        return ()
    peers: list[int] = []
    for proc in psutil.process_iter(attrs=("pid", "name", "cmdline")):
        try:
            info = proc.info
        except psutil.Error:
            continue
        if info["pid"] == self_pid:
            continue
        cmdline = info.get("cmdline") or ()
        if any("aeat" in str(token).lower() for token in cmdline):
            peers.append(int(info["pid"]))
    return tuple(sorted(peers))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args(argv)

    self_pid = os.getpid()
    for run_index in range(args.runs):
        observed_at = _now()
        peers = _peer_writer_pids(self_pid)
        report = _probe_secure_objects_integrity()
        for namespace_report in report.namespaces:
            record = {
                "run_index": run_index,
                "observed_at": observed_at,
                "observing_pid": self_pid,
                "peer_pids": list(peers),
                "namespace": namespace_report.namespace,
                "readable": namespace_report.readable,
                "unreadable": namespace_report.unreadable,
            }
            sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
