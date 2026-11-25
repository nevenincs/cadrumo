"""Per-file seconds from JUnit reports that a real nested pytest run wrote through the gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

from ..__main__ import main
from ..gate_graph import parse_gate_graph
from ..gate_runner import run_gate
from ..gate_timing import TIMING_NAME, TIMING_SCHEMA, GateTimingError, aggregate_timings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PROBE_TESTS = """\
import time


def test_quick():
    pass


class TestSlow:
    def test_sleeps(self):
        time.sleep(0.3)
"""


def _probe_tree(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    (tree / "suite").mkdir(parents=True)
    (tree / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (tree / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tree / "suite" / "test_probe.py").write_text(_PROBE_TESTS, encoding="utf-8")
    (tree / "suite" / "test_other.py").write_text("def test_other():\n    pass\n", encoding="utf-8")
    return tree


def _pytest_node(name: str, kind: str, tree: Path, target: str) -> dict[str, object]:
    # The repository's own JUnit plugin is loaded explicitly; the probe tree has
    # no conftest, and the runner's per-node report directory is what it reads.
    return {
        "name": name,
        "kind": kind,
        "command": [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-c",
            str(tree / "pytest.ini"),
            "--rootdir",
            str(tree),
            "-p",
            "dev.ci_reports",
            "-p",
            "no:cacheprovider",
            str(tree / target),
        ],
        "env": {
            "PYTHONPATH": str(REPO_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
    }


def test_timing_aggregates_each_nodes_real_junit_report_by_test_file(tmp_path: Path) -> None:
    tree = _probe_tree(tmp_path)
    graph = parse_gate_graph(
        {
            "schema": "cadrumo-gate-graph/v1",
            "node": [
                _pytest_node("parallel", "pytest-parallel", tree, "suite"),
                _pytest_node("serial", "pytest-serial", tree, "suite/test_probe.py"),
            ],
        }
    )
    record_dir = tmp_path / "record"

    result = run_gate(graph, budget=2, record_dir=record_dir, head_label="timing-head", tree_root=tree)

    assert result.status == "passed", (record_dir / "logs" / "parallel.log").read_text(encoding="utf-8")
    assert len(list((record_dir / "reports" / "parallel").glob("*.xml"))) == 1
    assert len(list((record_dir / "reports" / "serial").glob("*.xml"))) == 1

    timing = aggregate_timings(record_dir)

    assert timing["schema"] == TIMING_SCHEMA
    assert timing["head_label"] == "timing-head"
    assert timing["unresolved"] == {}
    files = timing["files"]
    assert isinstance(files, dict)
    assert list(files) == ["suite/test_other.py", "suite/test_probe.py"]
    nodes = timing["nodes"]
    assert isinstance(nodes, dict)
    assert nodes["parallel"]["tests"] == 3
    assert nodes["serial"]["tests"] == 2
    assert list(nodes["parallel"]["files"]) == ["suite/test_other.py", "suite/test_probe.py"]
    assert list(nodes["serial"]["files"]) == ["suite/test_probe.py"]
    # The sleeping test is measured once in each node; the file total is their sum.
    assert nodes["parallel"]["files"]["suite/test_probe.py"] >= 0.3
    assert nodes["serial"]["files"]["suite/test_probe.py"] >= 0.3
    assert files["suite/test_probe.py"] == pytest.approx(
        nodes["parallel"]["files"]["suite/test_probe.py"] + nodes["serial"]["files"]["suite/test_probe.py"],
        abs=0.002,
    )
    assert nodes["parallel"]["seconds"] >= nodes["parallel"]["files"]["suite/test_probe.py"]

    status = main(["gate-timing", "--record-dir", str(record_dir)])
    first = (record_dir / TIMING_NAME).read_bytes()
    second_path = tmp_path / "again.json"
    assert main(["gate-timing", "--record-dir", str(record_dir), "--output", str(second_path)]) == 0

    assert status == 0
    assert second_path.read_bytes() == first
    assert json.loads(first) == timing


def test_a_malformed_report_is_refused_rather_than_read_as_empty(tmp_path: Path) -> None:
    tree = _probe_tree(tmp_path)
    record_dir = tmp_path / "record"
    graph = parse_gate_graph(
        {
            "schema": "cadrumo-gate-graph/v1",
            "node": [{"name": "writes", "kind": "pytest-serial", "command": [sys.executable, "-c", "pass"]}],
        }
    )
    run_gate(graph, budget=1, record_dir=record_dir, head_label="h", tree_root=tree)
    (record_dir / "reports" / "writes" / "broken.xml").write_text("<testsuites><testcase", encoding="utf-8")

    with pytest.raises(GateTimingError, match="cannot be read"):
        aggregate_timings(record_dir)
