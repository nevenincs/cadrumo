"""Tripwire test that the built wheel bundles every shipped data file except corpus source binaries.

The corpus-registry packaging contract
relocates both data trees under ``src/cadrumo/_data/`` so the existing
``packages = ["src/cadrumo"]`` hatchling directive carries them inside
the wheel without any force-include declaration. The terminology tree
uses the same shipped-data contract. The wheel-split packaging decision
then excludes the corpus SOURCE binaries
(``_data/corpus/**/*.{pdf,docx,xls,xlsx,zip}``)
from this slim ``aeat`` wheel — they ship in the two separate ``aeat-data-*``
companion distributions — while every derived surface the runtime reads
(extracted text, normative html, registry, terminology, agent data) stays.
This test verifies that contract end-to-end by driving the real build pipeline:

1. ``uv build --wheel`` is invoked into a temporary output directory.
2. The resulting wheel archive is opened as a zip.
3. Every path reported by ``git ls-files`` under the shipped data
   subtrees, EXCEPT the excluded corpus source binaries, is asserted to
   appear in the archive at the corresponding ``cadrumo/_data/<relative-path>``
   prefix.
4. The corpus source binaries are asserted ABSENT from the slim wheel; the two
   ``aeat-data-*`` companion distributions are what carry them
   (``test_cadrumo_data_distribution`` proves that side).

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

from ._inventory import REPO_ROOT, SRC_CADRUMO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_CADRUMO / "_data"
_WHEEL_DATA_PREFIX = "cadrumo/_data"

# Corpus source binaries excluded from the slim ``aeat`` wheel (they ship in the
# two ``aeat-data-*`` companions). A path is an excluded corpus source binary
# when it lives under ``_data/corpus/`` and carries one of these suffixes.
# Mirrors the ``tool.hatch.build`` exclude patterns in ``pyproject.toml`` and
# the companion builders' suffix sets (``packaging/*/hatch_build.py``).
_CORPUS_BINARY_SUFFIXES = (".pdf", ".docx", ".xls", ".xlsx", ".zip")


def _is_corpus_source_binary(source_relative: str) -> bool:
    """Return True for a ``src/cadrumo/_data/corpus`` path that is an excluded source binary."""

    return source_relative.startswith("src/cadrumo/_data/corpus/") and source_relative.lower().endswith(
        _CORPUS_BINARY_SUFFIXES
    )


def _git_ls_files_data() -> list[str]:
    """Return git-tracked paths under ``src/cadrumo/_data`` relative to the project root."""

    completed = subprocess.run(
        [
            "git",
            "ls-files",
            "src/cadrumo/_data/corpus",
            "src/cadrumo/_data/registry",
            "src/cadrumo/_data/terminology",
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
    """Translate worktree paths to their expected wheel-archive locations.

    Excludes any ``tests/`` subtree under the shipped data root: the build
    config sheds
    every ``tests/`` package from the wheel — including the test-only
    ``corpus/tests`` module pool, which serves no installed consumer — and
    :mod:`test_wheel_content_boundary` is the dedicated gate proving that
    exclude end-to-end both ways. This gate's job is bundling parity for the
    shipped *functional* payload, so it must not expect the excluded test
    pool to appear in the archive.

    Also excludes the corpus source binaries
    (``_data/corpus/**/*.{pdf,docx,xls,xlsx,zip}``):
    the wheel-split decision moves them to the two ``aeat-data-*`` companions, so
    they are legitimately absent from this slim wheel and must not be expected here.
    """

    prefix = "src/cadrumo/_data/"
    expected: set[str] = set()
    for path in tracked:
        if not path.startswith(prefix):
            raise AssertionError(f"git ls-files returned a path outside src/cadrumo/_data/: {path!r}")
        if _is_corpus_source_binary(path):
            continue
        relative = path[len(prefix) :]
        if any(part == "tests" for part in Path(relative).parts):
            continue
        expected.add(f"{_WHEEL_DATA_PREFIX}/{relative}")
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
    wheels = sorted(out_dir.glob("cadrumo-*.whl"))
    if len(wheels) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
    return wheels[0]


def test_data_root_exists_in_worktree() -> None:
    """The relocated data root is present on disk before the wheel is built."""

    assert _DATA_ROOT.is_dir(), f"missing data root: {_DATA_ROOT}"


def test_wheel_filename_matches_distribution(built_wheel: Path) -> None:
    """The built wheel follows the expected ``cadrumo-<version>-py3-none-any.whl`` shape.

    The PyPI distribution is ``cadrumo`` (the import package stays ``cadrumo``), so
    the wheel filename normalises the distribution name to ``cadrumo`` — matching
    the ``cadrumo-*.whl`` glob the ``built_wheel`` fixture already uses.
    """

    assert re.match(r"^cadrumo-[0-9.]+(\.[a-z0-9]+)?-py3-none-any\.whl$", built_wheel.name), (
        f"unexpected wheel filename: {built_wheel.name}"
    )


def test_wheel_archive_contains_every_tracked_data_file(built_wheel: Path) -> None:
    """Every git-tracked file under src/cadrumo/_data appears inside the wheel archive."""

    tracked = _git_ls_files_data()
    expected = _expected_archive_paths(tracked)
    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    missing = sorted(expected - names)
    assert not missing, f"wheel is missing {len(missing)} bundled files; first ten: {missing[:10]!r}"


def test_wheel_excludes_renta_source_pdfs(built_wheel: Path) -> None:
    """The Renta ``source.pdf`` corpus binaries are absent from the slim wheel.

    They are corpus source binaries under ``corpus/manuals`` and ship in the
    ``aeat-data-manuals`` companion, not this wheel; asserting their absence pins
    the wheel-split boundary at exactly the highest-value binaries the prior
    contract force-shipped.
    """

    renta_pdfs = {
        f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/{year}/part1/source.pdf"
        for year in ("2020", "2021", "2022", "2023", "2024", "2025")
    }
    renta_pdfs.add(f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf")
    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    leaked = sorted(renta_pdfs & names)
    assert not leaked, (
        f"the slim wheel still ships Renta corpus source PDFs the wheel-split excludes: {leaked!r}; "
        "they belong in the aeat-data-manuals companion distribution"
    )


def test_wheel_ships_no_corpus_source_binaries(built_wheel: Path) -> None:
    """No ``_data/corpus`` pdf/docx/xls/xlsx/zip member survives in the slim wheel."""

    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}
    corpus_binaries = sorted(
        name
        for name in names
        if name.startswith(f"{_WHEEL_DATA_PREFIX}/corpus/") and name.lower().endswith(_CORPUS_BINARY_SUFFIXES)
    )
    assert not corpus_binaries, (
        f"the slim wheel ships {len(corpus_binaries)} corpus source binary member(s) the split excludes; "
        f"first ten: {corpus_binaries[:10]!r}"
    )
