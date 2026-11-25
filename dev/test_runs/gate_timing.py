"""Per-test-file seconds from a gate record's JUnit reports, for duration-balanced shards.

Each gate node writes its pytest JUnit reports into its own directory, so the
seconds here stay attributable to the node that measured them. A test file
measured by more than one node contributes the sum, because a shard plan
balances the whole cost of a file. The output is sorted JSON, stable for the
same reports.

A JUnit ``testcase`` names its module through ``classname`` (dotted path,
optionally followed by a class). The file is the longest dotted prefix that
names an existing ``.py`` file under the record's tree root; a classname that
names none is listed under ``unresolved`` rather than guessed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Final
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree

from cadrumo.core.atomic_write import atomic_write_text
from dev.paths import UTF_8

from .gate_runner import RECORD_NAME

TIMING_SCHEMA: Final = "cadrumo-gate-timing/v1"
TIMING_NAME: Final = "test-file-seconds.json"

_DECIMALS: Final = 3


class GateTimingError(ValueError):
    """The record or one of its reports cannot be read."""


def _test_file(classname: str, tree_root: Path, cache: dict[str, str | None]) -> str | None:
    if classname in cache:
        return cache[classname]
    parts = classname.split(".")
    found: str | None = None
    for length in range(len(parts), 0, -1):
        relative = "/".join(parts[:length]) + ".py"
        if (tree_root / relative).is_file():
            found = relative
            break
    cache[classname] = found
    return found


def _cases(report: Path) -> list[Element]:
    try:
        root = ElementTree.parse(report).getroot()
    except (ParseError, OSError) as exc:
        raise GateTimingError(f"JUnit report {report} cannot be read: {exc}") from exc
    if root is None:
        return []
    return list(root.iter("testcase"))


def _seconds(case: Element, report: Path) -> float:
    raw = case.get("time", "0")
    try:
        return float(raw)
    except ValueError as exc:
        raise GateTimingError(f"JUnit report {report} has a non-numeric time {raw!r}") from exc


def aggregate_timings(record_dir: Path) -> dict[str, object]:
    """Return per-file seconds overall and per node for the record in ``record_dir``."""
    try:
        record = json.loads((record_dir / RECORD_NAME).read_text(encoding=UTF_8))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateTimingError(f"no readable gate record in {record_dir}: {exc}") from exc
    tree_root = Path(record["tree_root"])
    cache: dict[str, str | None] = {}
    files: defaultdict[str, float] = defaultdict(float)
    unresolved: defaultdict[str, float] = defaultdict(float)
    nodes: dict[str, dict[str, object]] = {}
    for node in record["nodes"]:
        reports_dir = node.get("reports_dir")
        if not reports_dir:
            continue
        reports = sorted((record_dir / reports_dir).glob("*.xml"))
        node_files: defaultdict[str, float] = defaultdict(float)
        tests = 0
        total = 0.0
        for report in reports:
            for case in _cases(report):
                seconds = _seconds(case, report)
                tests += 1
                total += seconds
                path = case.get("file") or _test_file(case.get("classname", ""), tree_root, cache)
                if path is None:
                    unresolved[case.get("classname", "")] += seconds
                    continue
                node_files[path] += seconds
                files[path] += seconds
        nodes[node["name"]] = {
            "kind": node["kind"],
            "reports": len(reports),
            "tests": tests,
            "seconds": round(total, _DECIMALS),
            "files": _rounded(node_files),
        }
    return {
        "schema": TIMING_SCHEMA,
        "head_label": record.get("head_label"),
        "tree_digest": record.get("tree_digest", {}).get("start"),
        "files": _rounded(files),
        "nodes": dict(sorted(nodes.items())),
        "unresolved": _rounded(unresolved),
    }


def _rounded(values: dict[str, float]) -> dict[str, float]:
    return {key: round(values[key], _DECIMALS) for key in sorted(values)}


def write_timings(record_dir: Path, output: Path | None = None) -> Path:
    """Write the aggregation for ``record_dir`` and return where it went."""
    destination = output or record_dir / TIMING_NAME
    payload = aggregate_timings(record_dir)
    atomic_write_text(destination, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return destination
