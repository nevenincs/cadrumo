"""A retained snapshot cannot redirect incremental writes outside its owner."""

from pathlib import Path

import pytest

from ..product import _sync_source_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("linked_directory", [False, True])
def test_snapshot_refuses_links_before_changing_any_member(tmp_path: Path, linked_directory: bool) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "changed.py").write_text("new", encoding="utf-8")
    destination = tmp_path / "snapshot"
    destination.mkdir()
    (destination / "changed.py").write_text("old", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside if linked_directory else outside / "file.py"
    if not linked_directory:
        target.write_text("keep", encoding="utf-8")
    try:
        (destination / "link").symlink_to(target, target_is_directory=linked_directory)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(ValueError, match="snapshot contains a linked member"):
        _sync_source_snapshot(root, ("changed.py",), destination)
    assert (destination / "changed.py").read_text(encoding="utf-8") == "old"
    assert target.exists()
