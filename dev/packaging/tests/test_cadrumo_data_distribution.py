"""Packaging gate for the two ``cadrumo-data-*`` corpus companion distributions.

The wheel-split decision moves the corpus source binaries
(``_data/corpus/**/*.{pdf,xls,xlsx}``) out of the compact ``cadrumo`` wheel. Because
the full binary set exceeds PyPI's 100 MB per-file cap, it is split along the
corpus directory seam into TWO sub-cap companions, each under the cap so no size
grant is needed:

* ``cadrumo-data-manuals`` ships ``corpus/manuals``.
* ``cadrumo-data-official`` ships ``corpus/aeat_official``, ``corpus/eu_official``,
  and ``corpus/normatives``.

Both ship subtrees of the SAME ``cadrumo_data`` PEP 420 implicit namespace package
(NEITHER ships ``cadrumo_data/__init__.py``, which would collide on a joint
install), so ``importlib.resources.files("cadrumo_data")`` resolves a
``MultiplexedPath`` over both installed portions.

This gate builds both real companion wheels and asserts:

1. Each companion packages EXACTLY the git-tracked corpus source binaries under
   its owned subtree — no more, no fewer — each under the mirrored
   ``cadrumo_data/_data/corpus/<relative>`` path the runtime corpus-locator seam
   resolves.
2. The two companions are DISJOINT and their union equals the FULL tracked
   corpus-binary set — every binary the compact ``cadrumo`` wheel sheds is shipped by
   exactly one companion, and none twice.
3. Neither ships ``cadrumo_data/__init__.py`` (the namespace-package invariant) nor
   any corpus DERIVED surface (extracted text, html, json) — those stay in the
   ``cadrumo`` wheel.
4. Each version equals the root ``cadrumo`` distribution version, so a companion
   can only ship at the same version as the runtime wheel that resolves it.
5. Each built wheel is under PyPI's 100 MB per-file cap — the whole point of the
   split, asserted as a hard requirement.

The expected binary set is derived from the git-tracked source tree, not from
the wheels under test, so the parity assertion is not tautological. No mocks,
fakes, or skips: the real ``uv build`` pipeline runs, and a missing ``uv``/``git``
binary fails loudly.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
import zipfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..._paths import REPO_ROOT
from .._distribution_limits import PYPI_FILE_CAP_BYTES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT
_PACKAGING_ROOT = _REPO_ROOT / "packaging"
_CORPUS_SOURCE_PREFIX = "src/cadrumo/_data/corpus/"
_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip")
_COMPANION_CORPUS_PREFIX = "cadrumo_data/_data/corpus/"


@dataclass(frozen=True)
class _Companion:
    """One corpus companion distribution and the corpus subtrees it owns."""

    dist_name: str
    project_dir: str
    wheel_glob: str
    owned_subdirs: tuple[str, ...]


# The split contract: which corpus top-level subtrees each companion owns. The
# owned sets are disjoint and their union is every corpus subtree carrying source
# binaries; the exhaustiveness test proves that against the live tracked tree.
_COMPANIONS = (
    _Companion(
        dist_name="cadrumo-data-manuals",
        project_dir="cadrumo_data_manuals",
        wheel_glob="cadrumo_data_manuals-*.whl",
        owned_subdirs=("manuals",),
    ),
    _Companion(
        dist_name="cadrumo-data-official",
        project_dir="cadrumo_data_official",
        wheel_glob="cadrumo_data_official-*.whl",
        owned_subdirs=("aeat_official", "eu_official", "normatives"),
    ),
)


@dataclass(frozen=True)
class _BuiltWheel:
    """The archive members and on-disk byte size of one built companion wheel."""

    members: frozenset[str]
    size_bytes: int


@cache
def _tracked_corpus_binaries() -> set[str]:
    """Return git-tracked corpus source-binary paths relative to the repo root."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "src/cadrumo/_data/corpus/**/*.pdf",
            "src/cadrumo/_data/corpus/**/*.docx",
            "src/cadrumo/_data/corpus/**/*.xls",
            "src/cadrumo/_data/corpus/**/*.xlsm",
            "src/cadrumo/_data/corpus/**/*.xlsx",
            "src/cadrumo/_data/corpus/**/*.zip",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}
    # Mirror the companion build hooks: the Cadrumo wheel sheds every tests/ subtree,
    # so test-pool binaries are not runtime corpus data and the companions omit
    # them too.
    tracked = {path for path in tracked if "/tests/" not in path}
    if not tracked:
        raise AssertionError(
            "git ls-files reported no tracked corpus source binaries; the wheel-split contract has regressed"
        )
    return tracked


def _companion_member(tracked_path: str) -> str:
    """Map a tracked ``src/cadrumo/_data/corpus/...`` path to its companion archive path."""
    return f"{_COMPANION_CORPUS_PREFIX}{tracked_path.removeprefix(_CORPUS_SOURCE_PREFIX)}"


def _expected_members(companion: _Companion) -> set[str]:
    """Return the companion archive members expected for a companion's owned subtree."""
    owned_prefixes = tuple(f"{_CORPUS_SOURCE_PREFIX}{subdir}/" for subdir in companion.owned_subdirs)
    return {_companion_member(path) for path in _tracked_corpus_binaries() if path.startswith(owned_prefixes)}


def _pyproject_version(pyproject: Path) -> str:
    """Return the ``project.version`` string declared by a pyproject file."""
    with pyproject.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _build_wheel(companion: _Companion, out_root: Path) -> _BuiltWheel:
    """Build one companion wheel and return its members and byte size."""
    project_root = _PACKAGING_ROOT / companion.project_dir
    out_dir = out_root / companion.project_dir
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )
    wheels = scan_directory(out_dir, pattern=companion.wheel_glob)
    if len(wheels) != 1:
        raise AssertionError(
            f"expected exactly one {companion.wheel_glob} in {out_dir}; got {[w.name for w in wheels]!r}"
        )
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        members = frozenset(info.filename for info in archive.infolist())
    return _BuiltWheel(members=members, size_bytes=wheel.stat().st_size)


@pytest.fixture(scope="module")
def built_wheels(tmp_path_factory: pytest.TempPathFactory) -> dict[str, _BuiltWheel]:
    """Build both companion wheels once and return them keyed by distribution name."""
    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the Cadrumo-data distribution gate cannot run without the build driver",
        )
    out_root = tmp_path_factory.mktemp("cadrumo-data-wheels")
    return {companion.dist_name: _build_wheel(companion, out_root) for companion in _COMPANIONS}


def _corpus_members(built: _BuiltWheel) -> set[str]:
    """Return the corpus-tree members of a built wheel."""
    return {member for member in built.members if member.startswith(_COMPANION_CORPUS_PREFIX)}


def test_companion_packages_exactly_its_owned_subtree(built_wheels: dict[str, _BuiltWheel]) -> None:
    """Each companion carries every tracked binary under its owned subtree, and no other."""
    for companion in _COMPANIONS:
        expected = _expected_members(companion)
        assert expected, f"{companion.dist_name} owns no tracked corpus binaries; the split contract has regressed"
        shipped = _corpus_members(built_wheels[companion.dist_name])
        missing = sorted(expected - shipped)
        extra = sorted(shipped - expected)
        assert not missing, (
            f"{companion.dist_name} is missing {len(missing)} owned binaries; first ten: {missing[:10]!r}"
        )
        assert not extra, (
            f"{companion.dist_name} ships {len(extra)} corpus members outside its owned subtree; first ten: "
            f"{extra[:10]!r}"
        )


def test_companions_are_disjoint_and_exhaustive(built_wheels: dict[str, _BuiltWheel]) -> None:
    """The two companions share no member and together ship the full tracked corpus set."""
    manuals = _corpus_members(built_wheels["cadrumo-data-manuals"])
    official = _corpus_members(built_wheels["cadrumo-data-official"])
    overlap = sorted(manuals & official)
    assert not overlap, f"the two companions ship {len(overlap)} shared corpus member(s): {overlap[:10]!r}"

    union = manuals | official
    expected_full = {_companion_member(path) for path in _tracked_corpus_binaries()}
    missing = sorted(expected_full - union)
    extra = sorted(union - expected_full)
    assert not missing, (
        f"the companions together miss {len(missing)} tracked corpus binaries "
        f"(a binary shed by the root wheel that no data distribution ships); first ten: {missing[:10]!r}"
    )
    assert not extra, (
        f"the companions together ship {len(extra)} corpus members not in the tracked set; first ten: {extra[:10]!r}"
    )


def test_companion_ships_no_init_or_derived_member(built_wheels: dict[str, _BuiltWheel]) -> None:
    """No ``cadrumo_data/__init__.py`` (namespace invariant), derived surfaces, or foreign files."""
    for companion in _COMPANIONS:
        members = built_wheels[companion.dist_name].members
        assert "cadrumo_data/__init__.py" not in members, (
            f"{companion.dist_name} ships cadrumo_data/__init__.py; both companions must be PEP 420 namespace "
            "portions or a joint install collides on that path"
        )
        foreign = sorted(
            member
            for member in members
            if not member.startswith(_COMPANION_CORPUS_PREFIX) and ".dist-info/" not in member
        )
        assert not foreign, (
            f"{companion.dist_name} ships {len(foreign)} member(s) outside the corpus binary set: {foreign[:10]!r}"
        )
        derived = sorted(
            member
            for member in members
            if member.startswith(_COMPANION_CORPUS_PREFIX) and not member.lower().endswith(_CORPUS_BINARY_SUFFIXES)
        )
        assert not derived, (
            f"{companion.dist_name} ships {len(derived)} corpus DERIVED member(s) that belong in the Cadrumo wheel: "
            f"{derived[:10]!r}"
        )


def test_companion_version_matches_root_distribution() -> None:
    """Each companion version is locked to the root Cadrumo distribution version."""
    root_version = _pyproject_version(_REPO_ROOT / "pyproject.toml")
    for companion in _COMPANIONS:
        companion_version = _pyproject_version(_PACKAGING_ROOT / companion.project_dir / "pyproject.toml")
        assert companion_version == root_version, (
            f"{companion.dist_name} version {companion_version!r} does not match the root Cadrumo version "
            f"{root_version!r}; each companion must ship version-locked to the runtime wheel that resolves it — "
            "bump all together"
        )


def test_companion_wheel_is_under_the_pypi_file_cap(built_wheels: dict[str, _BuiltWheel]) -> None:
    """Each companion wheel stays under PyPI's 100 MB per-file cap — the reason for the split."""
    for companion in _COMPANIONS:
        size_bytes = built_wheels[companion.dist_name].size_bytes
        size_mb = size_bytes / 1_000_000
        assert size_bytes < PYPI_FILE_CAP_BYTES, (
            f"{companion.dist_name} wheel is {size_mb:.1f} MB, at or over PyPI's 100 MB per-file cap; the split "
            "exists precisely to keep each companion sub-cap without a size grant — the corpus seam partition must "
            "be rebalanced or a third companion carved"
        )
