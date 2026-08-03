"""Regression coverage for the shared directory byte-total walker.

:func:`~cadrumo.core.paths.directory_byte_total` converges the two
hand-rolled directory-tree byte summers found in
:mod:`cadrumo.core.observability` and
:mod:`cadrumo.application.bucket_maintenance`. These tests pin the shared
contract directly: a missing directory reports zero, a real file mid-walk
vanishing is tolerated only in ``tolerate_errors=True`` mode (and raises
otherwise), and the injectable ``entries`` seam is what makes that race
reproducible deterministically without mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..paths import directory_byte_total

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_missing_directory_reports_zero(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert directory_byte_total(missing) == (0, 0)


def test_sums_regular_files_recursively(tmp_path: Path) -> None:
    root = tmp_path / "d"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "a.bin").write_bytes(b"x" * 100)
    (nested / "b.bin").write_bytes(b"y" * 50)

    total_bytes, file_count = directory_byte_total(root)

    assert total_bytes == 150
    assert file_count == 2


def test_ignores_subdirectory_entries_in_the_total(tmp_path: Path) -> None:
    root = tmp_path / "d"
    (root / "nested").mkdir(parents=True)
    (root / "a.bin").write_bytes(b"x" * 10)

    total_bytes, file_count = directory_byte_total(root)

    assert total_bytes == 10
    assert file_count == 1


def test_tolerant_mode_skips_an_entry_that_vanished_mid_walk(tmp_path: Path) -> None:
    """A candidate deleted after enumeration but before stat is skipped, not fatal.

    The ``entries`` seam carries a genuinely-stale reference: ``doomed`` is
    unlinked from disk *after* being captured in the candidate list, so the
    function's ``.stat()`` call on it raises a real ``FileNotFoundError`` —
    no mock, a real race reproduced deterministically.
    """
    root = tmp_path / "d"
    root.mkdir()
    keep = root / "keep.bin"
    keep.write_bytes(b"x" * 100)
    doomed = root / "doomed.bin"
    doomed.write_bytes(b"y" * 50)
    entries = [keep, doomed]
    doomed.unlink()

    total_bytes, file_count = directory_byte_total(root, tolerate_errors=True, entries=entries)

    assert total_bytes == 100
    assert file_count == 1


def test_strict_mode_raises_on_an_entry_that_vanished_mid_walk(tmp_path: Path) -> None:
    """Anti-tautology companion: without ``tolerate_errors`` the same race raises.

    Proves the tolerant-mode test above is exercising real error-handling
    logic, not a code path that never raises in the first place.
    """
    root = tmp_path / "d"
    root.mkdir()
    doomed = root / "doomed.bin"
    doomed.write_bytes(b"y" * 50)
    entries = [doomed]
    doomed.unlink()

    with pytest.raises(OSError):
        directory_byte_total(root, tolerate_errors=False, entries=entries)


def test_strict_mode_is_the_default(tmp_path: Path) -> None:
    root = tmp_path / "d"
    root.mkdir()
    doomed = root / "doomed.bin"
    doomed.write_bytes(b"y" * 50)
    entries = [doomed]
    doomed.unlink()

    with pytest.raises(OSError):
        directory_byte_total(root, entries=entries)


def test_empty_directory_reports_zero(tmp_path: Path) -> None:
    root = tmp_path / "d"
    root.mkdir()
    assert directory_byte_total(root) == (0, 0)
