"""Proofs for the acquisition lane's guards and its download-free path, without downloading anything.

Each guard is shown to catch its defect against real files: a volume too full,
a removal outside the lane's own directory, a write to watched storage, and an
environment that would let the role reach real storage. The lane's own path
up to the download runs against conversations the real role recorded, replayed
on a real pipe through the real client, and against the built binary itself
where ``just test-components-role IMAGE`` names one. The interrupted setup, its
resume, the full check, the second run and the removal need a real download and
run only through ``python -m dev.smoke.acquisition_lane run --accept-size``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from cadrumo.tests.components_role_dispatch import RoleReplay
from cadrumo.tests.components_role_package import components_role_fixture, staged_components_role_fixture
from cadrumo.tests.components_role_replay import transcript_lines

from ..acquisition_lane import (
    DISK_MARGIN_BYTES,
    GIB,
    LaneRefusalError,
    LaneReport,
    fingerprint,
    fingerprint_changes,
    free_space_refusal,
    lane_parent,
    remove_scratch,
    role_environment,
    run_lane,
)

__all__ = ["components_role_fixture", "staged_components_role_fixture"]

pytestmark = [pytest.mark.hex_core]


def _build_directory(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    build.mkdir()
    (build / "build-paths.json").write_text(json.dumps({"paths": {"testing": "testing"}}), encoding="utf-8")
    return build


def _image(tmp_path: Path) -> Path:
    image = tmp_path / "cadrumo.exe"
    image.write_bytes(b"")
    return image


def _planned_bytes(name: str) -> int:
    (result,) = (json.loads(line) for line in transcript_lines(name) if json.loads(line)["type"] == "result")
    return int(result["plan"]["known_download_bytes"])


@pytest.mark.unit
def test_the_free_space_floor_is_the_plans_own_rule_plus_the_margin() -> None:
    assert free_space_refusal(free_bytes=GIB + DISK_MARGIN_BYTES, required_bytes=GIB) is None
    refusal = free_space_refusal(free_bytes=GIB + DISK_MARGIN_BYTES - 1, required_bytes=GIB)
    assert refusal is not None and str(GIB + DISK_MARGIN_BYTES) in refusal


@pytest.mark.unit
def test_the_lane_lives_in_the_build_trees_testing_directory_and_refuses_an_unconfigured_one(tmp_path: Path) -> None:
    build = _build_directory(tmp_path)
    assert lane_parent(build) == build / "testing" / "acquisition"
    with pytest.raises(LaneRefusalError, match="missing"):
        lane_parent(tmp_path / "unconfigured")


@pytest.mark.unit
def test_the_roles_environment_reaches_nothing_outside_the_root(tmp_path: Path) -> None:
    scratch = tmp_path / "run"
    base = {
        "PATH": "/usr/bin",
        "CADRUMO_LOCAL_STORAGE_ROOT": "/real/storage",
        "CADRUMO_PLAYWRIGHT_BROWSERS_DIR": "/real/browsers",
        "CADRUMO_PROXY_URL": "http://proxy.example:3128",
        "PLAYWRIGHT_BROWSERS_PATH": "/real/ms-playwright",
        "OLLAMA_MODELS": "/real/models",
        "HTTPS_PROXY": "http://proxy.example:3128",
        "LOCALAPPDATA": "/real/local",
        "HOME": "/real/home",
    }
    environment = role_environment(scratch, base)
    assert environment["PATH"] == "/usr/bin"
    assert Path(environment["CADRUMO_LOCAL_STORAGE_ROOT"]) == (scratch / "storage").resolve()
    for name in ("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "CADRUMO_PROXY_URL", "PLAYWRIGHT_BROWSERS_PATH", "OLLAMA_MODELS"):
        assert name not in environment, name
    assert not any(name.upper() == "HTTPS_PROXY" for name in environment)
    for name in ("LOCALAPPDATA", "HOME", "TEMP", "TMP"):
        assert Path(environment[name]).resolve().is_relative_to(scratch.resolve()), name


@pytest.mark.unit
def test_a_write_to_watched_storage_is_reported_and_reading_it_is_not(tmp_path: Path) -> None:
    watched = tmp_path / "components"
    watched.mkdir()
    (watched / "keep.txt").write_text("kept", encoding="utf-8")
    before = fingerprint([watched])
    assert fingerprint_changes(before, fingerprint([watched])) == []
    (watched / "added.zip").write_bytes(b"bytes")
    (watched / "keep.txt").write_text("changed!", encoding="utf-8")
    changes = fingerprint_changes(before, fingerprint([watched]))
    assert f"added {watched / 'added.zip'}" in changes
    assert f"changed {watched / 'keep.txt'}" in changes


@pytest.mark.unit
def test_the_root_is_removed_only_inside_the_lanes_own_directory(tmp_path: Path) -> None:
    parent = tmp_path / "acquisition"
    root = parent / "run-1"
    (root / "storage").mkdir(parents=True)
    (root / "storage" / "file.bin").write_bytes(b"x")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(LaneRefusalError, match="not a lane root"):
        remove_scratch(outside, parent=parent)
    assert outside.is_dir()
    assert remove_scratch(root, parent=parent) is True
    assert not root.exists()


def _replayed_lane(
    tmp_path: Path, transcripts: Mapping[str, Sequence[str]], *, free_bytes: int, accept_size: bool = False
) -> tuple[LaneReport, RoleReplay, Path]:
    replay = RoleReplay(transcripts)
    watched = tmp_path / "real-components"
    watched.mkdir()
    build = _build_directory(tmp_path)
    report = run_lane(
        ["browser"],
        accept_size=accept_size,
        image=_image(tmp_path),
        build_directory=build,
        start=replay,
        free_space=lambda _path: free_bytes,
        destinations=[watched],
    )
    return report, replay, lane_parent(build)


@pytest.mark.unit
def test_without_accepting_the_size_the_lane_plans_names_the_size_and_downloads_nothing(tmp_path: Path) -> None:
    report, replay, parent = _replayed_lane(
        tmp_path, {"status": ["status_quick_browser"], "plan": ["plan_every_item"]}, free_bytes=1 << 50
    )

    assert replay.commands() == [("status", "--item", "browser"), ("plan", "--item", "browser")]
    assert report.failures == []
    assert report.stopped_at_size is True and report.downloaded is False
    assert report.planned_bytes == _planned_bytes("plan_every_item")
    assert [step["step"] for step in report.steps] == ["status", "plan"]
    assert report.scratch_removed is True and list(parent.iterdir()) == []
    assert report.real_storage_changes == []
    for launch in replay.launches:
        root = Path(launch.environment["CADRUMO_LOCAL_STORAGE_ROOT"])
        assert root.parent.parent == parent.resolve(), "the role ran in the lane's throwaway root"


@pytest.mark.unit
def test_a_volume_too_full_for_the_plan_refuses_before_any_setup(tmp_path: Path) -> None:
    report, replay, parent = _replayed_lane(
        tmp_path,
        {"status": ["status_quick_browser"], "plan": ["plan_every_item"], "setup": ["setup_browser_completed"]},
        free_bytes=GIB,
        accept_size=True,
    )

    assert "setup" not in {launch.arguments[2] for launch in replay.launches}
    assert report.refused is not None and "bytes free" in report.refused
    assert report.downloaded is False
    assert report.scratch_removed is True and list(parent.iterdir()) == []


@pytest.mark.integration
@pytest.mark.external_tool
def test_the_real_role_plans_in_the_throwaway_root_and_leaves_nothing_behind(
    staged_components_role: Path, tmp_path: Path
) -> None:
    watched = tmp_path / "real-components"
    watched.mkdir()
    build = _build_directory(tmp_path)

    report = run_lane(["browser"], image=staged_components_role, build_directory=build, destinations=[watched])

    assert report.failures == [], report.failures
    assert report.refused is None, report.refused
    assert report.stopped_at_size is True and report.planned_bytes is not None and report.planned_bytes > 0
    assert report.plan_digest is not None and len(report.plan_digest) == 64
    assert report.scratch_removed is True and list(lane_parent(build).iterdir()) == []
