from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import lanes as lane_runner
from ..lanes import LaneResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_lane_transport_accepts_caller_owned_names_and_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: list[tuple[str, str]] = []

    def fake_run_lane(name: str, env: dict[str, str]) -> LaneResult:
        observed.append((name, env[lane_runner.RUN_ROOT_ENV]))
        status = 7 if name == "test-registry" else 0
        return LaneResult(name, status, 1)

    monkeypatch.setattr(lane_runner, "_run_lane", fake_run_lane)

    status = lane_runner.run_lanes(("test-unit", "test-registry"), repository=tmp_path)

    assert status == 7
    assert [name for name, _ in observed] == ["test-unit", "test-registry"]
    assert len({run_root for _, run_root in observed}) == 1
    run_root = Path(observed[0][1])
    assert run_root.parent.parent.name == "lane-runs"
    assert "-lanes-" in run_root.name
    assert all((run_root / child).is_dir() for child in lane_runner.RUN_SUBDIRECTORIES)
    log = (run_root / "run.log").read_text(encoding="utf-8")
    assert "lane run log" in log
    assert "test-all run log" not in log


@pytest.mark.parametrize(
    ("preflight_statuses", "failed_preflights", "expected_status"),
    (
        pytest.param({"collect": 2, "load": 0}, ("collect",), 2, id="collect-fails-load-passes"),
        pytest.param({"collect": 0, "load": 3}, ("load",), 3, id="collect-passes-load-fails"),
        pytest.param({"collect": 2, "load": 3}, ("collect", "load"), 2, id="both-preflights-fail"),
    ),
)
def test_preflight_prefix_runs_completely_then_blocks_execution_lanes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    preflight_statuses: dict[str, int],
    failed_preflights: tuple[str, ...],
    expected_status: int,
) -> None:
    observed: list[str] = []

    def fake_run_lane(name: str, _env: dict[str, str]) -> LaneResult:
        observed.append(name)
        return LaneResult(name, preflight_statuses.get(name, 0), 1)

    monkeypatch.setattr(lane_runner, "_run_lane", fake_run_lane)

    status = lane_runner.run_lanes(
        ("collect", "load", "parallel", "serial"),
        repository=tmp_path,
        json_events=True,
        persist_evidence=False,
        preflight_count=2,
        lane_kinds={"collect": "collection", "load": "load"},
    )

    assert status == expected_status
    assert observed == ["collect", "load"]
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert [(event["event"], event["lane"]) for event in events] == [
        ("lane_started", "collect"),
        ("lane_finished", "collect"),
        ("lane_started", "load"),
        ("lane_finished", "load"),
        ("lane_skipped", "parallel"),
        ("lane_skipped", "serial"),
    ]
    assert [event["kind"] for event in events] == [
        "collection",
        "collection",
        "load",
        "load",
        "command",
        "command",
    ]
    skipped = events[4:]
    assert [event["event"] for event in skipped] == ["lane_skipped", "lane_skipped"]
    assert [event["lane"] for event in skipped] == ["parallel", "serial"]
    assert [event["blocked_by"] for event in skipped] == [list(failed_preflights)] * 2
    assert all(event["reason"] == "preflight_failed" and event["role"] == "execution" for event in skipped)
