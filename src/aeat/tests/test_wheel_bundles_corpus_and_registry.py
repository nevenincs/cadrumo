"""Tripwire test that the built wheel bundles every git-tracked shipped data file.

The corpus-registry packaging contract
relocates both data trees under ``src/aeat/_data/`` so the existing
``packages = ["src/aeat"]`` hatchling directive carries them inside
the wheel without any force-include declaration. The terminology tree
uses the same shipped-data contract. This test verifies
that contract end-to-end by driving the real build pipeline:

1. ``uv build --wheel`` is invoked into a temporary output directory.
2. The resulting wheel archive is opened as a zip.
3. Every path reported by ``git ls-files`` under the shipped data
   subtrees is asserted to appear in the archive at the corresponding
   ``aeat/_data/<relative-path>`` prefix.

No mocks, fakes, or skips. If the worktree is missing the ``uv``
binary the test fails loudly so the locator's bundling guarantee is
never silently lost.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from ._inventory import REPO_ROOT, SRC_AEAT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_AEAT / "_data"
_WHEEL_DATA_PREFIX = "aeat/_data"


def _git_ls_files_data() -> list[str]:
    """Return git-tracked paths under ``src/aeat/_data`` relative to the project root."""

    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "src/aeat/_data/corpus",
            "src/aeat/_data/registry",
            "src/aeat/_data/terminology",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if not tracked:
        raise AssertionError(
            "git ls-files reported no tracked files under the shipped data trees; "
            "the data packaging contract has regressed or the worktree is detached",
        )
    return tracked


def _expected_archive_paths(tracked: list[str]) -> set[str]:
    """Translate worktree paths to their expected wheel-archive locations."""

    prefix = "src/aeat/_data/"
    expected: set[str] = set()
    for path in tracked:
        if not path.startswith(prefix):
            raise AssertionError(f"git ls-files returned a path outside src/aeat/_data/: {path!r}")
        expected.add(f"{_WHEEL_DATA_PREFIX}/{path[len(prefix) :]}")
    return expected


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the project wheel into a per-module temp directory and return the path."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; corpus-registry packaging guard "
            "cannot run without the project's build driver",
        )
    out_dir = tmp_path_factory.mktemp("wheel-out")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    wheels = sorted(out_dir.glob("aeat-*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"expected exactly one aeat-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
    return wheels[0]


def test_data_root_exists_in_worktree() -> None:
    """The relocated data root is present on disk before the wheel is built."""

    assert _DATA_ROOT.is_dir(), f"missing data root: {_DATA_ROOT}"


def test_wheel_filename_matches_distribution(built_wheel: Path) -> None:
    """The built wheel follows the expected ``aeat-<version>-py3-none-any.whl`` shape."""

    assert re.match(r"^aeat-[0-9.]+(\.[a-z0-9]+)?-py3-none-any\.whl$", built_wheel.name), (
        f"unexpected wheel filename: {built_wheel.name}"
    )


def test_wheel_archive_contains_every_tracked_data_file(built_wheel: Path) -> None:
    """Every git-tracked file under src/aeat/_data appears inside the wheel archive."""

    tracked = _git_ls_files_data()
    expected = _expected_archive_paths(tracked)
    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    missing = sorted(expected - names)
    assert not missing, f"wheel is missing {len(missing)} bundled files; first ten: {missing[:10]!r}"


def test_wheel_archive_includes_renta_pdf_allow_list(built_wheel: Path) -> None:
    """The seven gitignore-allow-listed Renta source.pdf files ship in the wheel."""

    expected_pdfs = {
        f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/{year}/part1/source.pdf"
        for year in ("2020", "2021", "2022", "2023", "2024", "2025")
    }
    expected_pdfs.add(f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf")
    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    missing = sorted(expected_pdfs - names)
    assert not missing, f"wheel is missing Renta allow-list PDFs: {missing!r}"
