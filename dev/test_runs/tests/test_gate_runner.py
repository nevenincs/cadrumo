"""The concurrent gate runner, exercised with real short child processes."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil
import pytest

from ..__main__ import main
from ..gate_graph import GateGraph, GateGraphError, parse_gate_graph
from ..gate_runner import RECORD_NAME, RECORD_SCHEMA, GateRunResult, run_gate
from ..gate_schedule import simulate_schedule
from ..lanes import lane_command_parser

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Sleep, then write ``start end`` nanosecond wall times to argv[1], then exit with argv[3].
_INTERVAL_PROBE = (
    "import pathlib, sys, time; s = time.time_ns(); time.sleep(float(sys.argv[2])); "
    "pathlib.Path(sys.argv[1]).write_text(f'{s} {time.time_ns()}'); raise SystemExit(int(sys.argv[3]))"
)


def _interval(probes: Path, name: str, seconds: float = 0.6, status: int = 0) -> list[str]:
    return [sys.executable, "-c", _INTERVAL_PROBE, str(probes / f"{name}.interval"), str(seconds), str(status)]


def _graph(*nodes: Mapping[str, object]) -> GateGraph:
    return parse_gate_graph({"schema": "cadrumo-gate-graph/v1", "node": list(nodes)})


def _tree(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / ".gitignore").write_text("out/\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    (tree / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    return tree


def _run(
    tmp_path: Path, graph: GateGraph, budget: int, *, tree: Path | None = None
) -> tuple[GateRunResult, dict[str, Any]]:
    result = run_gate(
        graph,
        budget=budget,
        record_dir=tmp_path / "record",
        head_label="probe-head",
        tree_root=tree or _tree(tmp_path),
    )
    record = json.loads((tmp_path / "record" / RECORD_NAME).read_text(encoding="utf-8"))
    return result, record


def _child_intervals(probes: Path) -> dict[str, tuple[int, int]]:
    intervals: dict[str, tuple[int, int]] = {}
    for path in probes.glob("*.interval"):
        start, end = path.read_text(encoding="utf-8").split()
        intervals[path.stem] = (int(start), int(end))
    return intervals


def _parent_intervals(record: dict[str, Any]) -> dict[str, tuple[float, float]]:
    intervals: dict[str, tuple[float, float]] = {}
    for node in record["nodes"]:
        if node["started_at"] is None:
            continue
        start = datetime.fromisoformat(node["started_at"]).timestamp()
        intervals[node["name"]] = (start, start + node["wall_seconds"])
    return intervals


def _peak_weight(intervals: dict[str, tuple[float, float]], weights: dict[str, int]) -> int:
    events = sorted(
        [(start, 1, name) for name, (start, _end) in intervals.items()]
        + [(end, 0, name) for name, (_start, end) in intervals.items()]
    )
    current = peak = 0
    for _at, starting, name in events:
        current += weights[name] if starting else -weights[name]
        peak = max(peak, current)
    return peak


def _overlap(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def test_running_weight_never_exceeds_the_budget_yet_nodes_overlap(tmp_path: Path) -> None:
    probes = tmp_path / "probes"
    probes.mkdir()
    weights = {"a": 2, "b": 1, "c": 2, "d": 1, "e": 1, "f": 2}
    graph = _graph(
        *(
            {"name": name, "kind": "static", "weight": weight, "command": _interval(probes, name)}
            for name, weight in weights.items()
        )
    )

    result, record = _run(tmp_path, graph, 3)

    assert result.status == "passed"
    assert result.exit_code == 0
    children = _child_intervals(probes)
    assert set(children) == set(weights)
    assert 2 <= _peak_weight({k: (float(s), float(e)) for k, (s, e) in children.items()}, weights) <= 3
    # The parent's spawn-to-reap interval contains each child's whole lifetime.
    assert _peak_weight(_parent_intervals(record), weights) <= 3


def test_after_and_exclusive_and_alone_are_honoured(tmp_path: Path) -> None:
    probes = tmp_path / "probes"
    probes.mkdir()
    graph = _graph(
        {"name": "first", "kind": "static", "command": _interval(probes, "first")},
        {"name": "follows", "kind": "static", "after": ["first"], "command": _interval(probes, "follows")},
        {"name": "lock-a", "kind": "build", "exclusive": ["docs"], "command": _interval(probes, "lock-a")},
        {"name": "lock-b", "kind": "build", "exclusive": ["docs"], "command": _interval(probes, "lock-b")},
        {"name": "free", "kind": "static", "command": _interval(probes, "free", 1.5)},
        {"name": "solo", "kind": "static", "alone": True, "command": _interval(probes, "solo", 0.3)},
        {"name": "late", "kind": "static", "command": _interval(probes, "late", 0.3)},
    )

    result, _record = _run(tmp_path, graph, 8)

    assert result.status == "passed"
    child = _child_intervals(probes)
    assert child["follows"][0] >= child["first"][1]
    assert not _overlap(child["lock-a"], child["lock-b"])
    assert _overlap(child["free"], child["lock-a"]) or _overlap(child["free"], child["lock-b"])
    assert not any(_overlap(child["solo"], interval) for name, interval in child.items() if name != "solo")


def test_a_red_node_does_not_stop_the_others_and_every_red_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    probes = tmp_path / "probes"
    probes.mkdir()
    graph = _graph(
        {"name": "red", "kind": "static", "command": _interval(probes, "red", 0.1, 3)},
        {"name": "green", "kind": "static", "after": ["red"], "command": _interval(probes, "green", 0.1)},
        {"name": "second-red", "kind": "static", "command": _interval(probes, "second-red", 0.4, 4)},
    )

    result, record = _run(tmp_path, graph, 1)

    assert result.status == "failed"
    assert result.exit_code == 3
    assert set(_child_intervals(probes)) == {"red", "green", "second-red"}
    verdicts = {node["name"]: (node["verdict"], node["exit_code"]) for node in record["nodes"]}
    assert verdicts == {"red": ("failed", 3), "green": ("passed", 0), "second-red": ("failed", 4)}
    err = capsys.readouterr().err
    assert "RED red: failed" in err
    assert "RED second-red: failed" in err


def test_a_failed_prerequisite_leaves_its_dependents_not_run(tmp_path: Path) -> None:
    probes = tmp_path / "probes"
    probes.mkdir()
    graph = _graph(
        {"name": "authority", "kind": "prerequisite", "command": _interval(probes, "authority", 0.1, 2)},
        {"name": "uses", "kind": "pytest-parallel", "after": ["authority"], "command": _interval(probes, "uses")},
        {"name": "then", "kind": "static", "after": ["uses"], "command": _interval(probes, "then")},
        {"name": "ordinary", "kind": "static", "command": _interval(probes, "ordinary", 0.1, 1)},
        {"name": "after-red", "kind": "static", "after": ["ordinary"], "command": _interval(probes, "after-red")},
    )

    result, record = _run(tmp_path, graph, 4)

    assert result.status == "failed"
    nodes = {node["name"]: node for node in record["nodes"]}
    assert set(_child_intervals(probes)) == {"authority", "ordinary", "after-red"}
    assert nodes["uses"]["verdict"] == "not_run"
    assert nodes["uses"]["blocked_by"] == ["authority"]
    assert nodes["then"]["verdict"] == "not_run"
    assert nodes["then"]["blocked_by"] == ["uses"]
    assert nodes["uses"]["log_path"] is None
    assert nodes["after-red"]["verdict"] == "passed"


def test_a_tree_that_moves_during_the_run_is_invalid_not_red_or_green(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    write = "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text(sys.argv[2])"
    graph = _graph(
        {
            "name": "ignored-output",
            "kind": "build",
            "command": [sys.executable, "-c", write, str(tree / "out" / "x"), "1"],
        }
    )
    (tree / "out").mkdir()
    (tmp_path / "still").mkdir()

    still, still_record = _run(tmp_path / "still", graph, 1, tree=tree)

    assert still.status == "passed"
    assert still_record["tree_digest"]["start"] == still_record["tree_digest"]["end"]

    moving = _graph(
        {
            "name": "edits-source",
            "kind": "static",
            "command": [sys.executable, "-c", write, str(tree / "source.py"), "VALUE = 2\n"],
        }
    )
    (tmp_path / "moving").mkdir()
    moved, moved_record = _run(tmp_path / "moving", moving, 1, tree=tree)

    assert moved.status == "invalid_tree_moved"
    assert moved.exit_code == 7
    assert moved_record["status"] == "invalid_tree_moved"
    assert moved_record["nodes"][0]["verdict"] == "passed"
    assert moved_record["tree_digest"]["start"] != moved_record["tree_digest"]["end"]


def test_the_record_keeps_each_node_attributable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CADRUMO_PYTEST_WORKERS", raising=False)
    monkeypatch.setenv("CADRUMO_CI_REPORT_NAME", "would-collide")
    show = (
        "import os; print('reports=' + os.environ['CADRUMO_CI_REPORTS_DIR']); "
        "print('workers=' + os.environ.get('CADRUMO_PYTEST_WORKERS', '-')); "
        "print('name=' + os.environ.get('CADRUMO_CI_REPORT_NAME', '-')); print('extra=' + os.environ['PROBE_EXTRA'])"
    )
    graph = _graph(
        {
            "name": "parallel",
            "kind": "pytest-parallel",
            "weight": 3,
            "command": [sys.executable, "-c", show],
            "env": {"PROBE_EXTRA": "p"},
        },
        {
            "name": "serial",
            "kind": "pytest-serial",
            "weight": 1,
            "workers": 0,
            "command": [sys.executable, "-c", show],
            "env": {"PROBE_EXTRA": "s"},
        },
        {
            "name": "static",
            "kind": "static",
            "command": [sys.executable, "-c", show + "; raise SystemExit(1)"],
            "env": {"PROBE_EXTRA": "x"},
        },
    )

    result, record = _run(tmp_path, graph, 4)

    record_dir = (tmp_path / "record").resolve()
    assert result.record_path == record_dir / RECORD_NAME
    assert record["schema"] == RECORD_SCHEMA
    assert record["head_label"] == "probe-head"
    assert record["budget"] == 4
    assert record["status"] == "failed"
    assert record["exit_code"] == 1
    assert record["tree_digest"]["start"] == record["tree_digest"]["end"] is not None
    nodes = {node["name"]: node for node in record["nodes"]}
    assert [node["name"] for node in record["nodes"]] == ["parallel", "serial", "static"]
    expected = {"parallel": ("passed", "3", "p"), "serial": ("passed", "0", "s"), "static": ("failed", "-", "x")}
    for name, (verdict, workers, extra) in expected.items():
        node = nodes[name]
        assert node["verdict"] == verdict
        assert node["weight"] == (3 if name == "parallel" else 1)
        assert node["wall_seconds"] > 0
        assert datetime.fromisoformat(node["started_at"]).tzinfo is not None
        assert node["log_path"] == f"logs/{name}.log"
        assert node["reports_dir"] == f"reports/{name}"
        log = (record_dir / node["log_path"]).read_text(encoding="utf-8").splitlines()
        assert f"reports={record_dir / 'reports' / name}" in log
        assert f"workers={workers}" in log
        assert f"extra={extra}" in log
        assert "name=-" in log
        assert (record_dir / node["reports_dir"]).is_dir()


def test_a_missing_executable_is_a_red_node_with_the_missing_tool_status(tmp_path: Path) -> None:
    graph = _graph({"name": "absent", "kind": "static", "command": ["cadrumo-no-such-tool-anywhere"]})

    result, record = _run(tmp_path, graph, 1)

    assert result.exit_code == 127
    assert record["nodes"][0]["verdict"] == "failed"
    assert "was not found" in (tmp_path / "record" / "logs" / "absent.log").read_text(encoding="utf-8")


def test_an_existing_record_is_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / "record").mkdir()
    (tmp_path / "record" / RECORD_NAME).write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError):
        run_gate(
            _graph({"name": "a", "kind": "static", "command": [sys.executable, "-c", "pass"]}),
            budget=1,
            record_dir=tmp_path / "record",
            head_label="h",
            tree_root=_tree(tmp_path),
        )
    assert (tmp_path / "record" / RECORD_NAME).read_text(encoding="utf-8") == "{}"


_SPAWNER = (
    "import pathlib, subprocess, sys, time; "
    "child = subprocess.Popen([sys.executable, '-c', "
    "'import os, pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(120)', "
    "sys.argv[1]]); time.sleep(float(sys.argv[2]))"
)


def _wait_for(path: Path) -> int:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if path.is_file() and (text := path.read_text(encoding="utf-8")):
            return int(text)
        time.sleep(0.05)
    raise AssertionError(f"{path} never appeared")


def test_an_interruption_stops_only_the_process_trees_the_gate_started(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    graph = _graph(
        {"name": "spawner", "kind": "static", "command": [sys.executable, "-c", _SPAWNER, str(pid_file), "120"]},
        {"name": "waiting", "kind": "static", "after": ["spawner"], "command": [sys.executable, "-c", "pass"]},
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    stop = threading.Event()
    outcome: list[GateRunResult] = []
    tree = _tree(tmp_path)
    runner = threading.Thread(
        target=lambda: outcome.append(
            run_gate(graph, budget=1, record_dir=tmp_path / "record", head_label="h", tree_root=tree, stop=stop)
        )
    )
    try:
        runner.start()
        grandchild = psutil.Process(_wait_for(pid_file))
        # Let the runner observe the grandchild in its periodic descendant scan.
        time.sleep(1.5)
        stop.set()
        runner.join(timeout=60)
        assert not runner.is_alive()
        assert not grandchild.is_running() or grandchild.status() == psutil.STATUS_ZOMBIE
        assert unrelated.poll() is None
    finally:
        unrelated.kill()
        unrelated.wait()
    result = outcome[0]
    assert result.status == "interrupted"
    assert result.exit_code == 130
    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in record["nodes"]}
    assert (nodes["spawner"]["verdict"], nodes["spawner"]["cause"]) == ("failed", "interrupted")
    assert (nodes["waiting"]["verdict"], nodes["waiting"]["cause"]) == ("not_run", "interrupted")


def test_descendants_left_behind_by_a_finished_node_are_stopped_after_the_grace(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    graph = _graph(
        {"name": "leaves-one", "kind": "static", "command": [sys.executable, "-c", _SPAWNER, str(pid_file), "2"]}
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        result = run_gate(
            graph,
            budget=1,
            record_dir=tmp_path / "record",
            head_label="h",
            tree_root=_tree(tmp_path),
            descendant_grace_seconds=0.5,
        )
        assert unrelated.poll() is None
    finally:
        unrelated.kill()
        unrelated.wait()

    record = json.loads(result.record_path.read_text(encoding="utf-8"))
    grandchild_pid = int(pid_file.read_text(encoding="utf-8"))
    assert result.status == "passed"
    assert record["nodes"][0]["stray_processes_stopped"] >= 1
    assert not psutil.pid_exists(grandchild_pid) or psutil.Process(grandchild_pid).status() == psutil.STATUS_ZOMBIE


def test_only_selects_named_nodes_and_the_prerequisites_they_follow() -> None:
    graph = _graph(
        {"name": "seed", "kind": "prerequisite", "command": ["x"]},
        {"name": "publish", "kind": "prerequisite", "after": ["seed"], "command": ["x"]},
        {"name": "lint", "kind": "static", "command": ["x"]},
        {"name": "unit", "kind": "pytest-parallel", "after": ["publish", "lint"], "command": ["x"]},
    )

    selected = graph.select(("unit",))

    assert [node.name for node in selected.nodes] == ["seed", "publish", "unit"]
    assert selected.node("unit").after == ("publish",)
    with pytest.raises(GateGraphError, match="unknown nodes"):
        graph.select(("missing",))


@pytest.mark.parametrize(
    ("node", "message"),
    (
        pytest.param({"name": "a", "kind": "static", "command": ["x"], "after": ["a"]}, "follows itself", id="self"),
        pytest.param({"name": "a", "kind": "static", "command": ["x"], "after": ["z"]}, "unknown nodes", id="unknown"),
        pytest.param({"name": "a", "kind": "lint", "command": ["x"]}, "kind must be", id="kind"),
        pytest.param({"name": "a", "kind": "static", "command": []}, "command", id="empty-command"),
        pytest.param({"name": "a", "kind": "static", "command": ["x"], "weight": 0}, "weight", id="weight"),
        pytest.param({"name": "a", "kind": "static", "command": ["x"], "workers": 2}, "not a pytest", id="workers"),
        pytest.param({"name": "a", "kind": "static", "command": ["x"], "colour": 1}, "unknown keys", id="key"),
        pytest.param(
            {"name": "a", "kind": "static", "command": ["x"], "env": {"CADRUMO_PYTEST_WORKERS": "9"}},
            "runner owns",
            id="owned-env",
        ),
        pytest.param({"name": "../a", "kind": "static", "command": ["x"]}, "name", id="path-name"),
    ),
)
def test_a_malformed_node_is_refused(node: dict[str, object], message: str) -> None:
    with pytest.raises(GateGraphError, match=message):
        _graph(node)


def test_cycles_and_oversized_nodes_are_refused() -> None:
    with pytest.raises(GateGraphError, match="cycle"):
        _graph(
            {"name": "a", "kind": "static", "command": ["x"], "after": ["b"]},
            {"name": "b", "kind": "static", "command": ["x"], "after": ["a"]},
        )
    with pytest.raises(GateGraphError, match="more than the budget"):
        _graph({"name": "a", "kind": "static", "command": ["x"], "weight": 5}).check_budget(4)


def test_the_dry_run_prints_the_policy_schedule_without_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = tmp_path / "ran"
    touch = [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"]
    graph_file = tmp_path / "graph.json"
    graph_file.write_text(
        json.dumps(
            {
                "schema": "cadrumo-gate-graph/v1",
                "node": [
                    {"name": "prep", "kind": "prerequisite", "command": touch},
                    {"name": "wide", "kind": "pytest-parallel", "weight": 3, "after": ["prep"], "command": touch},
                    {"name": "narrow", "kind": "static", "weight": 1, "command": touch},
                    {"name": "bench", "kind": "static", "alone": True, "after": ["wide"], "command": touch},
                ],
            }
        ),
        encoding="utf-8",
    )

    status = main(["gate", "--graph", str(graph_file), "--budget", "4", "--dry-run"])

    assert status == 0
    assert not marker.exists()
    lines = [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip().startswith("step")]
    assert lines == [
        "step 1: weight 2/4: prep[prerequisite w1], narrow[static w1]",
        "step 2: weight 3/4: wide[pytest-parallel w3]",
        "step 3: weight 1/4: bench[static w1]",
    ]
    waves = simulate_schedule(parse_gate_graph(json.loads(graph_file.read_text(encoding="utf-8"))), 4)
    assert [[node.name for node in wave] for wave in waves] == [["prep", "narrow"], ["wide"], ["bench"]]


def test_the_cli_runs_a_toml_graph_into_the_record_directory(tmp_path: Path) -> None:
    graph_file = tmp_path / "graph.toml"
    graph_file.write_text(
        'schema = "cadrumo-gate-graph/v1"\n\n'
        "[[node]]\n"
        'name = "ok"\n'
        'kind = "static"\n'
        f'command = [{json.dumps(sys.executable)}, "-c", "print(\'ok\')"]\n',
        encoding="utf-8",
    )
    tree = _tree(tmp_path)

    status = main(
        [
            "gate",
            "--graph",
            str(graph_file),
            "--budget",
            "2",
            "--record-dir",
            str(tmp_path / "record"),
            "--head-label",
            "cli-head",
            "--tree-root",
            str(tree),
            "--json-events",
        ]
    )

    assert status == 0
    record = json.loads((tmp_path / "record" / RECORD_NAME).read_text(encoding="utf-8"))
    assert record["head_label"] == "cli-head"
    assert record["graph"]["path"] == str(graph_file)
    assert len(record["graph"]["sha256"]) == 64
    assert record["nodes"][0]["verdict"] == "passed"


def test_a_gate_command_line_names_no_lanes_for_the_recipe_reachability_reader() -> None:
    parsed, _ = lane_command_parser().parse_known_args(["gate", "--graph", "g.toml", "--budget", "4"])

    assert parsed.lane == []
