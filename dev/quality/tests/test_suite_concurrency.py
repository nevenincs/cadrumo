"""Concurrent execution in the quality suite: every red reported, declared order kept, CMake never shared.

The gates here are real processes. Overlap is observed by the processes
themselves: each marks itself running and records whether it saw its peer
running at the same time, so the assertions read what actually happened.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final

import pytest

from .. import suite
from ..suite import CMAKE_CONFIGURE, Gate, run_gates

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Marks itself started and waits (up to a bound) for its peer to start. A peer
#: that started and has not finished is running at the same time: the probe
#: records the overlap and then waits for the peer to see it too, so neither
#: side can finish before the other has looked. The probe finishes only after
#: a peer it saw has finished or seen it, then exits with the requested status.
_PROBE: Final[str] = """\
import pathlib, sys, time
directory, me, peer = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
wait, status = float(sys.argv[4]), int(sys.argv[5])
mark = lambda name, state: directory / f"{name}.{state}"
mark(me, "started").write_text("", encoding="utf-8")
deadline = time.monotonic() + wait
while time.monotonic() < deadline and not mark(peer, "started").exists():
    time.sleep(0.02)
if mark(peer, "started").exists():
    if not mark(peer, "finished").exists():
        mark(me, "overlapped").write_text("", encoding="utf-8")
    while time.monotonic() < deadline and not (mark(peer, "overlapped").exists() or mark(peer, "finished").exists()):
        time.sleep(0.02)
mark(me, "finished").write_text("", encoding="utf-8")
print(f"{me} finished")
raise SystemExit(status)
"""


def _probe(tmp_path: Path) -> Path:
    path = tmp_path / "probe.py"
    path.write_text(_PROBE, encoding="utf-8")
    return path


def _gate(
    probe: Path,
    directory: Path,
    me: str,
    peer: str,
    *,
    wait: float,
    status: int = 0,
    resources: frozenset[str] = frozenset(),
) -> Gate:
    return Gate(me, (sys.executable, str(probe), str(directory), me, peer, str(wait), str(status)), resources)


def test_gates_run_concurrently_up_to_the_job_bound(tmp_path: Path) -> None:
    probe, directory = _probe(tmp_path), tmp_path / "markers"
    directory.mkdir()
    gates = [_gate(probe, directory, "left", "right", wait=120), _gate(probe, directory, "right", "left", wait=120)]

    outcomes = run_gates(gates, jobs=2)

    assert [outcome.result.status for outcome in outcomes] == ["passed", "passed"]
    assert (directory / "left.overlapped").exists() or (directory / "right.overlapped").exists()


def test_the_default_of_one_job_runs_gates_one_after_another(tmp_path: Path) -> None:
    probe, directory = _probe(tmp_path), tmp_path / "markers"
    directory.mkdir()
    gates = [_gate(probe, directory, "left", "right", wait=0.5), _gate(probe, directory, "right", "left", wait=0.5)]

    run_gates(gates)

    assert not list(directory.glob("*.overlapped"))


def test_gates_sharing_the_cmake_configure_resource_never_overlap(tmp_path: Path) -> None:
    """Detector teeth: the same pair without the resource does overlap, so the probe can see it."""
    probe = _probe(tmp_path)
    exclusive, free = tmp_path / "exclusive", tmp_path / "free"
    exclusive.mkdir()
    free.mkdir()
    cmake = frozenset({CMAKE_CONFIGURE})

    run_gates(
        [
            _gate(probe, exclusive, "check-frontend", "check-rust", wait=1.5, resources=cmake),
            _gate(probe, exclusive, "check-rust", "check-frontend", wait=1.5, resources=cmake),
        ],
        jobs=2,
    )
    run_gates(
        [
            _gate(probe, free, "check-frontend", "check-rust", wait=120),
            _gate(probe, free, "check-rust", "check-frontend", wait=120),
        ],
        jobs=2,
    )

    assert not list(exclusive.glob("*.overlapped"))
    assert list(free.glob("*.overlapped"))


def test_both_native_gates_hold_the_cmake_configure_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(suite, "resolve_just_executable", lambda: "just-fixture")

    gates, unavailable = suite.native_gates("Release")

    assert unavailable == []
    assert [(gate.name, gate.command, gate.resources) for gate in gates] == [
        ("check-frontend", ("just-fixture", "check-frontend", "Release"), frozenset({CMAKE_CONFIGURE})),
        ("check-rust", ("just-fixture", "check-rust", "Release"), frozenset({CMAKE_CONFIGURE})),
    ]


def test_every_red_is_reported_in_declared_order_with_the_first_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The slow first gate finishes last, yet its failure is still reported first and sets the status."""
    probe, directory = _probe(tmp_path), tmp_path / "markers"
    directory.mkdir()
    monkeypatch.setattr(
        suite,
        "GATES",
        (
            ("slow-red", _gate(probe, directory, "slow-red", "fast-red", wait=120, status=3).command),
            ("fast-red", _gate(probe, directory, "fast-red", "absent", wait=0, status=1).command),
            ("green", _gate(probe, directory, "green", "absent", wait=0).command),
        ),
    )
    report = tmp_path / "report.json"

    assert suite.main(jobs=3, report=report) == 3

    output = capsys.readouterr().out
    assert output.index("FAIL  slow-red") < output.index("FAIL  fast-red")
    assert "slow-red finished" in output
    assert "fast-red finished" in output
    timing_lines = [line.split()[-1] for line in output.splitlines() if line.startswith(("passed", "failed"))]
    assert timing_lines == ["slow-red", "fast-red", "green"]
    recorded = json.loads(report.read_text(encoding="utf-8"))
    assert recorded["exit_status"] == 3
    assert recorded["jobs"] == 3
    assert [(row["name"], row["status"], row["returncode"]) for row in recorded["gates"]] == [
        ("slow-red", "failed", 3),
        ("fast-red", "failed", 1),
        ("green", "passed", 0),
    ]
    assert all(isinstance(row["seconds"], float) and row["seconds"] > 0 for row in recorded["gates"])


def test_a_job_bound_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        run_gates([], jobs=0)
