"""Identities are keyed by content: unchanged inputs keep theirs, concurrent builds share one."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..build_stamp import (
    HISTORY,
    STAMP_NAME,
    BuildStamp,
    ComponentIdentity,
    Freeze,
    allocate,
    build_type,
    display_version,
    image_environment,
    load_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

DAY = datetime(2026, 10, 19, 8, 30, tzinfo=UTC)
NEXT_DAY = datetime(2026, 10, 20, 0, 0, 1, tzinfo=UTC)


def content(label: object) -> str:
    return hashlib.sha256(str(label).encode()).hexdigest()


@pytest.fixture(autouse=True)
def _build_time_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    # A reproducible-build environment would replace the build time these cases supply.
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)


def test_unchanged_content_keeps_its_identity_and_leaves_the_counter(tmp_path: Path) -> None:
    first = allocate(tmp_path, "manager", content("a"), now=DAY)
    registry = (tmp_path / STAMP_NAME).read_bytes()
    assert allocate(tmp_path, "manager", content("a"), now=NEXT_DAY) == first
    assert (tmp_path / STAMP_NAME).read_bytes() == registry
    assert first == BuildStamp("2026101901", 1, "2026-10-19T08:30:00Z")


def test_changed_content_takes_the_next_iteration_and_sequence(tmp_path: Path) -> None:
    stamps = [allocate(tmp_path, "manager", content(n), now=DAY) for n in range(3)]
    stamps.append(allocate(tmp_path, "manager", content(3), now=NEXT_DAY))
    assert [stamp.build_id for stamp in stamps] == ["2026101901", "2026101902", "2026101903", "2026102001"]
    assert [stamp.build_sequence for stamp in stamps] == [1, 2, 3, 4]


def test_components_count_on_one_directory_counter_and_keep_separate_identities(tmp_path: Path) -> None:
    manager = allocate(tmp_path, "manager", content("shared"), now=DAY)
    desktop = allocate(tmp_path, "desktop", content("shared"), now=DAY)
    assert (manager.build_sequence, desktop.build_sequence) == (1, 2)
    changed = allocate(tmp_path, "desktop", content("frontend edit"), now=DAY)
    assert changed.build_sequence == 3
    assert allocate(tmp_path, "manager", content("shared"), now=DAY) == manager


def test_returning_to_earlier_content_reuses_its_identity_within_the_history(tmp_path: Path) -> None:
    original = allocate(tmp_path, "interpreter", content("original"), now=DAY)
    allocate(tmp_path, "interpreter", content("edited"), now=DAY)
    assert allocate(tmp_path, "interpreter", content("original"), now=DAY) == original
    for n in range(HISTORY):
        allocate(tmp_path, "interpreter", content(n), now=DAY)
    assert allocate(tmp_path, "interpreter", content("original"), now=DAY) != original


def test_the_iteration_grows_past_99_without_truncation(tmp_path: Path) -> None:
    for n in range(99):
        allocate(tmp_path, "manager", content(n), now=DAY)
    assert allocate(tmp_path, "manager", content("hundredth"), now=DAY).build_id == "20261019100"


def test_explicit_values_freeze_every_identity(tmp_path: Path) -> None:
    allocate(tmp_path, "manager", content("a"), now=DAY)
    freeze = Freeze(number=412, build_id="2026101942", date="2026-10-19T09:00:00Z")
    frozen = [allocate(tmp_path, key, content("b"), freeze=freeze, now=DAY) for key in ("manager", "package")]
    assert frozen[0] == frozen[1] == BuildStamp("2026101942", 412, "2026-10-19T09:00:00Z")
    number_only = allocate(tmp_path, "desktop", content("c"), freeze=Freeze(number=7), now=DAY)
    assert (number_only.build_id, number_only.build_sequence) == ("2026101904", 7)
    with pytest.raises(ValueError, match="between 1 and 65535"):
        Freeze(number=65536)


def test_source_date_epoch_dates_a_new_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(int(NEXT_DAY.timestamp())))
    stamp = allocate(tmp_path, "manager", content("a"), now=DAY)
    assert (stamp.build_id, stamp.build_date) == ("2026102001", "2026-10-20T00:00:01Z")


def test_the_sequence_refuses_to_pass_the_windows_file_version_limit(tmp_path: Path) -> None:
    allocate(tmp_path, "manager", content("a"), now=DAY)
    state = json.loads((tmp_path / STAMP_NAME).read_text(encoding="utf-8"))
    (tmp_path / STAMP_NAME).write_text(json.dumps({**state, "sequence": 65534}), encoding="utf-8")
    assert allocate(tmp_path, "manager", content("b"), now=DAY).build_sequence == 65535
    with pytest.raises(ValueError, match="reached 65535"):
        allocate(tmp_path, "manager", content("c"), now=DAY)
    # Already-allocated content still resolves at the limit.
    assert allocate(tmp_path, "manager", content("b"), now=DAY).build_sequence == 65535


def test_a_per_invocation_counter_continues_without_repeating_numbers(tmp_path: Path) -> None:
    previous = {"schema": 1, "day": "20261019", "iteration": 25, "sequence": 25, "build_id": "2026101925"}
    (tmp_path / STAMP_NAME).write_text(json.dumps(previous), encoding="utf-8")
    assert allocate(tmp_path, "manager", content("a"), now=DAY) == BuildStamp("2026101926", 26, "2026-10-19T08:30:00Z")


def _allocate(directory: Path, label: str) -> tuple[str, int]:
    stamp = allocate(directory, "manager", content(label), now=DAY)
    return stamp.build_id, stamp.build_sequence


def test_concurrent_processes_with_the_same_inputs_share_one_identity(tmp_path: Path) -> None:
    with ProcessPoolExecutor(max_workers=6) as pool:
        allocated = set(pool.map(_allocate, [tmp_path] * 18, ["same"] * 18))
    assert allocated == {("2026101901", 1)}


def test_concurrent_threads_with_the_same_inputs_share_one_identity(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        allocated = set(pool.map(_allocate, [tmp_path] * 24, ["same"] * 24))
    assert allocated == {("2026101901", 1)}


def test_concurrent_builds_with_different_inputs_never_share_an_identity(tmp_path: Path) -> None:
    with ProcessPoolExecutor(max_workers=4) as pool:
        allocated = list(pool.map(_allocate, [tmp_path] * 12, [str(n) for n in range(12)]))
    assert sorted(sequence for _, sequence in allocated) == list(range(1, 13))
    assert sorted(build_id for build_id, _ in allocated) == [f"20261019{n:02d}" for n in range(1, 13)]


def test_a_missing_identity_names_its_remedy(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="build the targets that compile it"):
        load_identity(tmp_path / "manager.json")


def test_display_version_build_type_and_component_variables() -> None:
    assert build_type("Debug") == "debug"
    assert build_type("Release") == "release"
    with pytest.raises(ValueError, match="RelWithDebInfo"):
        build_type("RelWithDebInfo")
    assert display_version("0.6.0", "2026101903", "release") == "0.6.0+2026101903"
    assert display_version("0.6.0", "2026101903", "debug") == "0.6.0+2026101903.debug"
    assert BuildStamp("2026101903", 412, "2026-10-19T08:30:00Z").environment("manager") == {
        "CADRUMO_MANAGER_BUILD_ID": "2026101903",
        "CADRUMO_MANAGER_BUILD_SEQUENCE": "412",
        "CADRUMO_MANAGER_BUILD_DATE": "2026-10-19T08:30:00Z",
    }
    identity = ComponentIdentity("installer", "0" * 64, "0.6.0", BuildStamp("2026101904", 4, "2026-10-19T08:30:00Z"))
    assert image_environment(identity) == {
        "CADRUMO_IMAGE_COMPONENT": "installer",
        "CADRUMO_INSTALLER_BUILD_ID": "2026101904",
        "CADRUMO_INSTALLER_BUILD_SEQUENCE": "4",
        "CADRUMO_INSTALLER_BUILD_DATE": "2026-10-19T08:30:00Z",
    }
