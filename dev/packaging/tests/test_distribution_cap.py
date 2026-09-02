"""The publish path's size refusal, and the limit it reaches for.

These exercise the real module against real files on disk rather than a mocked
``stat``: the whole point of the check is that it measures what was actually
built, and a test that stubbed the size would police nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._distribution_limits import PYPI_FILE_CAP_BYTES
from ..distribution_cap import built_distributions, oversize_distributions

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _sized(path: Path, size: int) -> Path:
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


def test_a_distribution_under_the_cap_is_accepted(tmp_path: Path) -> None:
    _sized(tmp_path / "cadrumo-0.1.0-py3-none-any.whl", PYPI_FILE_CAP_BYTES - 1)
    assert oversize_distributions(tmp_path) == []


def test_a_distribution_exactly_at_the_cap_is_refused(tmp_path: Path) -> None:
    """The limit is inclusive: PyPI rejects a file *at* the cap, not only over it."""
    boundary = _sized(tmp_path / "cadrumo-0.1.0.tar.gz", PYPI_FILE_CAP_BYTES)
    assert oversize_distributions(tmp_path) == [boundary]


def test_the_marker_uv_build_leaves_behind_is_not_a_distribution(tmp_path: Path) -> None:
    """``uv build`` writes a ``.gitignore`` beside the artifacts it produces.

    Counting it would report a cleared distribution that no index would ever
    receive, and an output directory holding only that marker would pass a
    check that is supposed to fail closed on an empty build.
    """
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")
    assert built_distributions(tmp_path) == []


def test_only_uploadable_suffixes_are_measured(tmp_path: Path) -> None:
    wheel = _sized(tmp_path / "cadrumo-0.1.0-py3-none-any.whl", 16)
    sdist = _sized(tmp_path / "cadrumo-0.1.0.tar.gz", 16)
    _sized(tmp_path / "cadrumo-0.1.0.whl.sha256", PYPI_FILE_CAP_BYTES)
    assert built_distributions(tmp_path) == sorted((wheel, sdist))
