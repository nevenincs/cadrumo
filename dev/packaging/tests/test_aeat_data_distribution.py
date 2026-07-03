"""Packaging gate for the ``aeat-data`` corpus companion distribution.

The wheel-split decision moves the corpus source binaries
(``_data/corpus/**/*.{pdf,xls,xlsx}``) out of the slim ``aeat`` wheel and into a
separate ``aeat-data`` companion. This gate proves the companion side of that
boundary end-to-end by building the real companion wheel and asserting:

1. It packages EXACTLY the git-tracked corpus source binaries — no more, no
   fewer — each under the mirrored ``aeat_data/_data/corpus/<relative>`` path the
   runtime corpus-locator seam resolves.
2. It ships NOTHING else besides the ``aeat_data/__init__.py`` package root and
   the wheel ``.dist-info`` metadata — in particular none of the corpus DERIVED
   surfaces (extracted text, html, json), which stay in the ``aeat`` wheel.
3. Its version equals the root ``aeat`` distribution version, so the companion
   can only ship at the same version as the runtime wheel that resolves it.

The expected binary set is derived from the git-tracked source tree, not from
the wheel under test, so the parity assertion is not tautological. No mocks,
fakes, or skips: the real ``uv build`` pipeline runs, and a missing ``uv``/``git``
binary fails loudly.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPANION_ROOT = _REPO_ROOT / "packaging" / "aeat_data"
_CORPUS_SOURCE_PREFIX = "src/aeat/_data/corpus/"
_CORPUS_BINARY_SUFFIXES = (".pdf", ".xls", ".xlsx")
_COMPANION_CORPUS_PREFIX = "aeat_data/_data/corpus/"


def _tracked_corpus_binaries() -> set[str]:
    """Return git-tracked corpus source-binary paths relative to the repo root."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "src/aeat/_data/corpus/**/*.pdf",
            "src/aeat/_data/corpus/**/*.xls",
            "src/aeat/_data/corpus/**/*.xlsx",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    # Mirror the companion build hook: the aeat wheel sheds every tests/ subtree,
    # so test-pool binaries are not runtime corpus data and the companion omits
    # them too.
    tracked = {path for path in tracked if "/tests/" not in path}
    if not tracked:
        raise AssertionError(
            "git ls-files reported no tracked corpus source binaries; the wheel-split contract has regressed"
        )
    return tracked


def _pyproject_version(pyproject: Path) -> str:
    """Return the ``project.version`` string declared by a pyproject file."""
    with pyproject.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


@pytest.fixture(scope="module")
def companion_members() -> frozenset[str]:
    """Build the aeat-data companion wheel and return its archive member paths."""
    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the aeat-data distribution gate cannot run without the build driver",
        )
    out_dir = _COMPANION_ROOT / "dist-test"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    try:
        subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
            cwd=_COMPANION_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        wheels = sorted(out_dir.glob("aeat_data-*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"expected exactly one aeat_data-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
        with zipfile.ZipFile(wheels[0]) as archive:
            return frozenset(info.filename for info in archive.infolist())
    finally:
        if out_dir.exists():
            shutil.rmtree(out_dir)


def test_companion_packages_exactly_the_tracked_corpus_binaries(companion_members: frozenset[str]) -> None:
    """The companion carries every tracked corpus binary under a mirrored path, and no other."""
    expected = {
        f"{_COMPANION_CORPUS_PREFIX}{path.removeprefix(_CORPUS_SOURCE_PREFIX)}" for path in _tracked_corpus_binaries()
    }
    shipped_corpus = {member for member in companion_members if member.startswith(_COMPANION_CORPUS_PREFIX)}
    missing = sorted(expected - shipped_corpus)
    extra = sorted(shipped_corpus - expected)
    assert not missing, f"companion is missing {len(missing)} tracked corpus binaries; first ten: {missing[:10]!r}"
    assert not extra, (
        f"companion ships {len(extra)} corpus members not in the tracked binary set; first ten: {extra[:10]!r}"
    )


def test_companion_ships_no_derived_or_foreign_members(companion_members: frozenset[str]) -> None:
    """The companion carries only corpus binaries, the package root, and dist-info metadata."""
    foreign = sorted(
        member
        for member in companion_members
        if not member.startswith(_COMPANION_CORPUS_PREFIX)
        and member != "aeat_data/__init__.py"
        and ".dist-info/" not in member
    )
    assert not foreign, (
        f"companion ships {len(foreign)} member(s) outside the corpus binary set and package scaffold: {foreign[:10]!r}"
    )
    derived = sorted(
        member
        for member in companion_members
        if member.startswith(_COMPANION_CORPUS_PREFIX) and not member.lower().endswith(_CORPUS_BINARY_SUFFIXES)
    )
    assert not derived, (
        f"companion ships {len(derived)} corpus DERIVED member(s) that belong in the aeat wheel: {derived[:10]!r}"
    )


def test_companion_version_matches_root_distribution() -> None:
    """The aeat-data version is locked to the root aeat distribution version."""
    companion_version = _pyproject_version(_COMPANION_ROOT / "pyproject.toml")
    root_version = _pyproject_version(_REPO_ROOT / "pyproject.toml")
    assert companion_version == root_version, (
        f"aeat-data version {companion_version!r} does not match the root aeat version {root_version!r}; "
        "the companion must ship version-locked to the runtime wheel that resolves it — bump both together"
    )
