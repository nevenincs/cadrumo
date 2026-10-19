"""The lane admits a stage by its build records, reports later edits, and refuses an outdated test host."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest

from ..freshness import STAGED_COMPONENTS, built_from, host_part, newer_source, stage_verdict, stale_parts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILT = 1_800_000_000_000_000_000
_SECOND = 1_000_000_000
_OLD = _BUILT - 10 * _SECOND
_NEW = _BUILT + 10 * _SECOND


def _write(path: Path, *, at: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, ns=(at, at))
    return path


@pytest.mark.parametrize(
    ("relative", "built"),
    [
        ("native/desktop/src-tauri/src/manager.rs", True),
        ("native/desktop/frontend/src/App.tsx", True),
        ("Y:/code/agent/src/cadrumo_agent/service.py", True),
        ("native/desktop/src-tauri/src/manager/tests.rs", False),
        ("native/desktop/src-tauri/src/shell/setup/track_tests.rs", False),
        ("native/desktop/frontend/tests/live/attach.live.ts", False),
        ("native/desktop/frontend/src/components/Rail.stories.tsx", False),
        ("native/desktop/frontend/src/shell/agentCatalog.test.ts", False),
        ("src/cadrumo/core/tests/test_hashing.py", False),
    ],
)
def test_only_files_built_into_the_product_count_as_its_sources(relative: str, built: bool) -> None:
    assert built_from(relative) is built


def test_the_newest_source_changed_after_the_artifact_is_named(tmp_path: Path) -> None:
    artifact = _write(tmp_path / "image.exe", at=_BUILT)
    older = _write(tmp_path / "a.rs", at=_BUILT - _SECOND)
    newer = _write(tmp_path / "b.rs", at=_BUILT + _SECOND)
    newest = _write(tmp_path / "c.rs", at=_BUILT + 2 * _SECOND)
    assert newer_source(artifact, [older]) is None
    assert newer_source(artifact, [older, newer, newest, tmp_path / "removed.rs"]) == newest


class _Stage:
    """A staged package and the build records of its components, as their builds would leave them."""

    def __init__(self, root: Path) -> None:
        self.build = root / "build"
        self.package = self.build / "stage" / "Debug" / "app"
        self.records: dict[str, dict[str, Any]] = {}
        self.edited: dict[str, list[str]] = {}
        for index, component in enumerate(STAGED_COMPONENTS):
            artifact = _write(self.package / f"{component}.bin", at=_BUILT)
            artifact.write_bytes(component.encode())
            self.records[component] = {
                "schema": 1,
                "component": component,
                "state": "settled",
                "build_id": f"20261019{index}",
                "staged": {
                    "Debug": {
                        "package": "stage/Debug/app",
                        "artifacts": {f"{component}.bin": hashlib.sha256(component.encode()).hexdigest()},
                    }
                },
            }

    def verdict(self) -> Any:
        return stage_verdict(
            self.build,
            "Debug",
            read_record=lambda _build, component: self.records.get(component),
            changed_inputs=lambda _build, component: self.edited.get(component, []),
        )


def test_a_stage_its_records_vouch_for_is_admitted(tmp_path: Path) -> None:
    verdict = _Stage(tmp_path).verdict()
    assert verdict.refusals == []
    assert verdict.snapshot["app-payload"] == "202610193"
    assert verdict.changed == {}


def test_edits_after_staging_are_reported_and_do_not_refuse(tmp_path: Path) -> None:
    stage = _Stage(tmp_path)
    stage.edited["app-agent"] = ["Y:/agent/src/cadrumo_agent/service.py"]
    verdict = stage.verdict()
    assert verdict.refusals == []
    assert verdict.changed == {"app-agent": ["Y:/agent/src/cadrumo_agent/service.py"]}


def test_a_rebuild_that_left_an_output_unchanged_is_current(tmp_path: Path) -> None:
    # The image predates an edited source, but its bytes are the ones its build recorded.
    stage = _Stage(tmp_path)
    os.utime(stage.package / "interpreter.bin", ns=(_OLD, _OLD))
    assert stage.verdict().refusals == []


def test_staged_bytes_that_differ_from_their_record_are_refused(tmp_path: Path) -> None:
    stage = _Stage(tmp_path)
    (stage.package / "desktop.bin").write_bytes(b"another build's image")
    (refusal,) = stage.verdict().refusals
    assert refusal.startswith("desktop's staged bytes are not the ones build 202610192 recorded")
    assert refusal.endswith("rebuild with: just build-native Debug app-native")


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda record: record.update(state="unsettled"), "app-payload's build is unsettled, not settled"),
        (lambda record: record.update(state="building"), "app-payload's build is building, not settled"),
        (lambda record: record.update(staged={}), "app-payload records nothing staged for Debug"),
    ],
)
def test_an_unsettled_or_unstaged_record_is_refused(tmp_path: Path, change: Any, expected: str) -> None:
    stage = _Stage(tmp_path)
    change(stage.records["app-payload"])
    (refusal,) = stage.verdict().refusals
    assert refusal.startswith(expected)
    assert refusal.endswith("just build-native Debug app-payload")


def test_a_component_with_no_record_is_refused(tmp_path: Path) -> None:
    stage = _Stage(tmp_path)
    del stage.records["manager"]
    assert stage.verdict().refusals == ["manager has no build record; rebuild with: just build-native Debug app-native"]


def test_the_test_host_is_refused_when_older_than_its_sources(tmp_path: Path) -> None:
    repository = tmp_path / "checkout"
    record = _write(tmp_path / "build" / "desktop" / "testing" / "packaged" / "host.json", at=_BUILT)
    source = _write(repository / "native/desktop/src-tauri/src/app.rs", at=_OLD)
    _write(repository / "native/desktop/src-tauri/src/app/tests.rs", at=_NEW)
    assert stale_parts([host_part(record, repository)]) == ([], [])
    os.utime(source, ns=(_NEW, _NEW))
    stale, missing = stale_parts([host_part(record, repository)])
    assert missing == []
    assert [(part.part, part.source, part.target) for part in stale] == [("test host", source, "desktop-packaged-host")]
