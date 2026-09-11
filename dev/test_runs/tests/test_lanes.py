from __future__ import annotations

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
