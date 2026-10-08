"""Candidate and source caches share the structural gate's module lifetime."""

from __future__ import annotations

from pathlib import Path

import pytest

from .inventory import python_files_under, read_source, release_parsed_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_module_boundary_rediscovers_added_and_removed_sources(tmp_path: Path) -> None:
    """An isolated mutable tree exercises the module release, not a live edit."""
    old = tmp_path / "old.py"
    old.write_text("before = 1\n", encoding="utf-8")
    assert python_files_under(tmp_path) == (old,)
    assert read_source(old) == "before = 1\n"
    old.unlink()
    new = tmp_path / "new.py"
    new.write_text("after = 2\n", encoding="utf-8")

    release_parsed_sources()

    assert python_files_under(tmp_path) == (new,)
    assert read_source(new) == "after = 2\n"
    with pytest.raises(FileNotFoundError):
        read_source(old)


def test_a_missing_source_within_a_gate_is_not_silently_filtered(tmp_path: Path) -> None:
    """Refreshing between modules does not exempt a disappearance mid-scan."""
    source = tmp_path / "candidate.py"
    source.write_text("value = 1\n", encoding="utf-8")
    (candidate,) = python_files_under(tmp_path)
    source.unlink()

    with pytest.raises(FileNotFoundError):
        read_source(candidate)
