"""Build cache reuse must bind all output bytes, not merely their lengths."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ..action_cache import completed, current, modified_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_reuse_rejects_same_size_mutation(tmp_path: Path) -> None:
    payload = tmp_path / "runtime.dll"
    payload.write_bytes(b"original")
    completed(tmp_path, "target-one")
    assert current(tmp_path, "target-one")
    assert not current(tmp_path, "target-two")
    payload.write_bytes(b"modified")
    assert not current(tmp_path, "target-one")


def test_reuse_rejects_added_or_missing_files(tmp_path: Path) -> None:
    payload = tmp_path / "runtime.dll"
    payload.write_bytes(b"original")
    completed(tmp_path, "identity")
    added = tmp_path / "unexpected.pth"
    added.write_text("import unwanted", encoding="utf-8")
    assert not current(tmp_path, "identity")
    added.unlink()
    assert current(tmp_path, "identity")
    payload.unlink()
    assert not current(tmp_path, "identity")


def test_old_size_only_markers_are_not_reused(tmp_path: Path) -> None:
    (tmp_path / "ready").write_text('{"inputs":"identity","outputs":{}}', encoding="utf-8")
    assert not current(tmp_path, "identity")


def test_schema_two_markers_require_a_new_link_aware_inventory(tmp_path: Path) -> None:
    (tmp_path / "ready").write_text('{"schema":2,"inputs":"identity","outputs":{}}', encoding="utf-8")
    assert not current(tmp_path, "identity")


def test_contained_sdk_links_are_bound_to_text_and_target_bytes(tmp_path: Path) -> None:
    library = tmp_path / "sdk/lib"
    library.mkdir(parents=True)
    payload = library / "libpython.so.1.0"
    payload.write_bytes(b"original")
    link = library / "libpython.so"
    try:
        link.symlink_to("libpython.so.1.0")
        (tmp_path / "sdk/aliases").symlink_to("lib", target_is_directory=True)
    except OSError:
        pytest.skip("The runner cannot create SDK symlinks")
    completed(tmp_path, "identity")
    assert current(tmp_path, "identity")
    state = json.loads((tmp_path / "ready").read_text(encoding="utf-8"))
    assert state["schema"] == 3
    assert list(state["outputs"]["files"]) == ["sdk/lib/libpython.so.1.0"]
    assert state["outputs"]["links"]["sdk/lib/libpython.so"]["text"] == "libpython.so.1.0"
    assert state["outputs"]["links"]["sdk/lib/libpython.so"]["target"] == "sdk/lib/libpython.so.1.0"
    link.unlink()
    link.symlink_to(payload)
    assert not current(tmp_path, "identity")
    completed(tmp_path, "identity")
    payload.write_bytes(b"modified")
    assert not current(tmp_path, "identity")


@pytest.mark.parametrize("defect", ["escape", "cycle"])
def test_sdk_link_escape_or_cycle_cannot_complete_or_reuse(tmp_path: Path, defect: str) -> None:
    cache = tmp_path / "runtime"
    cache.mkdir()
    (cache / "payload").write_bytes(b"SDK bytes")
    completed(cache, "identity")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside if defect == "escape" else cache
    try:
        (cache / "linked").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("The runner cannot create SDK symlinks")
    assert not current(cache, "identity")
    with pytest.raises(ValueError, match=r"escapes the selected SDK|directory link cycle"):
        completed(cache, "identity")


def test_modified_inputs_names_edited_and_removed_inputs_only(tmp_path: Path) -> None:
    steady, edited, removed, extra = (tmp_path / name for name in ("steady", "edited", "removed", "extra"))
    for path in (steady, edited, removed, extra):
        path.write_text("before", encoding="utf-8")
    listing = tmp_path / "inputs.txt"
    listing.write_text("\n".join(str(path) for path in (steady, edited, removed)), encoding="utf-8")
    started = steady.stat().st_mtime_ns + 1_000_000_000
    os.utime(steady, ns=(started - 1, started - 1))
    os.utime(extra, ns=(started - 1, started - 1))
    edited.write_text("after", encoding="utf-8")
    os.utime(edited, ns=(started, started))
    removed.unlink()
    assert modified_inputs(listing, (extra,), started) == [edited, removed]
