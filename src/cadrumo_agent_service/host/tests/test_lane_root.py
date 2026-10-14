"""Only a root marked for itself is a development agent lane root."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ..lane_root import LANE_MARK_NAME, is_marked_lane_root, write_lane_mark

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_freshly_marked_empty_root_is_a_lane_root(tmp_path: Path) -> None:
    root = tmp_path / "lane"
    root.mkdir()
    mark = write_lane_mark(root)
    assert mark.name == LANE_MARK_NAME
    assert is_marked_lane_root(root)


def test_an_unmarked_root_is_not_a_lane_root(tmp_path: Path) -> None:
    assert not is_marked_lane_root(tmp_path)


def test_a_root_already_in_use_cannot_be_marked(tmp_path: Path) -> None:
    (tmp_path / "profiles").mkdir()
    with pytest.raises(ValueError, match="empty"):
        write_lane_mark(tmp_path)
    assert not (tmp_path / LANE_MARK_NAME).exists()


def test_a_mark_copied_into_another_root_does_not_admit_it(tmp_path: Path) -> None:
    lane = tmp_path / "lane"
    other = tmp_path / "other"
    lane.mkdir()
    other.mkdir()
    write_lane_mark(lane)
    shutil.copy(lane / LANE_MARK_NAME, other / LANE_MARK_NAME)
    assert is_marked_lane_root(lane)
    assert not is_marked_lane_root(other)


@pytest.mark.parametrize(
    "document",
    (
        {"schema": 2, "kind": "cadrumo.agent_development_lane"},
        {"schema": 1, "kind": "something_else"},
        {"schema": 1, "kind": "cadrumo.agent_development_lane", "extra": True},
    ),
)
def test_a_malformed_mark_does_not_admit_the_root(tmp_path: Path, document: dict[str, object]) -> None:
    root = tmp_path / "lane"
    root.mkdir()
    (root / LANE_MARK_NAME).write_text(json.dumps({**document, "root": str(root.resolve())}), encoding="utf-8")
    assert not is_marked_lane_root(root)


def test_the_per_user_default_root_is_never_a_lane_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "default"
    default.mkdir()
    monkeypatch.setattr("cadrumo_agent_service.host.lane_root.host_installed_default_root", lambda _environ: default)
    with pytest.raises(ValueError, match="default"):
        write_lane_mark(default)
    (default / LANE_MARK_NAME).write_text(
        json.dumps({"schema": 1, "kind": "cadrumo.agent_development_lane", "root": str(default.resolve())}),
        encoding="utf-8",
    )
    assert not is_marked_lane_root(default)
