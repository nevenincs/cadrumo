"""Regression coverage for the path-keyed single-file cache-fingerprint helper.

:func:`~cadrumo.core.paths.path_stat_fingerprint` converges the inline
resolve-then-stat boilerplate found across roughly a dozen single-file
loader modules (schema, IVA rate, recargo-band, category-profile,
manual-chapter, record-design, XML-dictionary, and PDF-text loaders), each
of which previously built its own ``(str(resolved), stat.st_size,
stat.st_mtime_ns)`` cache-key triple by hand. It is the path-keyed sibling
of :func:`~cadrumo.core.paths.file_stat_fingerprint` (which keys on the bare
file name, correct only for a same-directory tree fingerprint).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..paths import path_stat_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_returns_the_full_path_string_size_and_mtime_ns(tmp_path: Path) -> None:
    target = tmp_path / "a.toml"
    target.write_bytes(b"x" * 42)

    path_str, size, mtime_ns = path_stat_fingerprint(target)

    assert path_str == str(target)
    assert size == 42
    assert mtime_ns == target.stat().st_mtime_ns


def test_two_same_named_files_in_different_directories_fingerprint_differently(tmp_path: Path) -> None:
    """The whole point of the path-keyed sibling: a bare-name key would collide here."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "same.toml").write_bytes(b"same size")
    (right / "same.toml").write_bytes(b"same size")

    left_fp = path_stat_fingerprint(left / "same.toml")
    right_fp = path_stat_fingerprint(right / "same.toml")

    assert left_fp != right_fp
    assert left_fp[0] != right_fp[0]


def test_a_content_change_changes_the_fingerprint(tmp_path: Path) -> None:
    target = tmp_path / "a.toml"
    target.write_bytes(b"v1")
    before = path_stat_fingerprint(target)

    target.write_bytes(b"v2-longer")

    after = path_stat_fingerprint(target)
    assert before != after
    assert before[1] != after[1]  # size changed


def test_a_missing_file_raises_oserror(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.toml"

    with pytest.raises(OSError):
        path_stat_fingerprint(missing)
