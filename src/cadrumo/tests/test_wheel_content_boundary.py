"""Packaging content-boundary gate: the wheel sheds tests and corpus binaries, keeps payload.

The build config excludes
every ``tests/`` tree from the installed wheel — those modules and fixtures
serve no installed consumer, since the suites run from the repository tree —
and the corpus SOURCE binaries (``_data/corpus/**/*.{pdf,xls,xlsx}``), which the
wheel-split decision moves to the two ``aeat-data-*`` companions. This gate
proves the boundary end-to-end by building the real wheel and asserting it every
way:

1. No ``tests/`` member ships (the exclude took effect), so the ~11 MB fixture
   payload no longer reaches consumers.
2. No corpus source binary (``*.pdf``/``*.xls``/``*.xlsx`` under ``_data/corpus``)
   ships — the 94%-of-weight payload the split sheds to the ``aeat-data-*``
   companions.
3. The required functional payload still ships — the ``_data`` roots (corpus,
   registry, terminology), the ``py.typed`` marker, the BIP-39 recovery
   wordlist, and ``external_constants.toml`` — so the exclude cannot silently
   strip something the installed package needs.
4. The corpus DERIVED surfaces the runtime reads (extracted text
   ``*.extracted.md``/``.json`` and normative html) survive: the corpus-binary
   exclude must shed only the source binaries, never the derived payload.

The exclude alone is build config that can silently rot; this post-build
assertion is what makes the boundary an executable contract. No mocks, fakes,
or skips: the real ``uv build`` pipeline runs, and a missing ``uv`` binary
fails loudly.
"""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory
from .inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WHEEL_PREFIX = "cadrumo"
_WHEEL_DATA_PREFIX = "cadrumo/_data"
_WHEEL_CORPUS_PREFIX = f"{_WHEEL_DATA_PREFIX}/corpus/"
# Members the build backend places in an archive on its own behalf whatever the
# project declares: its own generated metadata, and the version-control ignore
# file hatchling ships so a rebuild from the archive reproduces. Both survive an
# explicit exclude, so they are recognised rather than fought.
_BUILD_BACKEND_MEMBERS = frozenset({"PKG-INFO", ".gitignore"})


def _wheel_root(member: str) -> str:
    """The wheel member's top-level name, with the backend's version stamp trimmed.

    ``cadrumo/`` and ``cadrumo-<version>.dist-info/`` are both the product's own.
    """
    return Path(member).parts[0].partition("-")[0]


def _sdist_root(member: str) -> str:
    """The sdist member's top-level name, matched whole.

    Not version-trimmed: an sdist's top-level members are real filenames, and
    trimming would read ``PKG-INFO`` as ``PKG``.
    """
    return Path(member).parts[0]


def _declared_sdist_roots() -> frozenset[str]:
    """The top-level names the build configuration declares the sdist ships.

    Derived from the declaration rather than restated here. A restated list is
    the construct that falls behind what it describes: it would keep passing
    over content the build configuration no longer ships, and would fail over
    content it legitimately added. Reading the declaration makes the archive
    answerable to the same authority that produced it.
    """
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = config["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    return frozenset(Path(entry).parts[0] for entry in declared)


# Corpus source binaries the wheel-split excludes; they ship in the two
# ``aeat-data-*`` companions, so zero of them may appear in this slim wheel.
_CORPUS_BINARY_SUFFIXES = (".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip")

# Required functional payload that MUST survive the tests exclude. Each entry is
# a wheel-archive path (or, for the data roots, a directory prefix probed below).
_REQUIRED_DATA_ROOTS = (
    "corpus",
    "registry",
    "terminology",
)
_REQUIRED_MEMBERS = (
    f"{_WHEEL_PREFIX}/py.typed",
    f"{_WHEEL_PREFIX}/adapters/persistence/storage/_bip39_wordlist.txt",
    f"{_WHEEL_PREFIX}/core/external_constants.toml",
)


@pytest.fixture(scope="module")
def wheel_members(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """Build the project wheel and return the set of archive member paths."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the packaging content-boundary gate "
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
    wheels = scan_directory(out_dir, pattern="cadrumo-*.whl")
    if len(wheels) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
    with zipfile.ZipFile(wheels[0]) as archive:
        return frozenset(info.filename for info in archive.infolist())


@pytest.fixture(scope="module")
def sdist_members(tmp_path_factory: pytest.TempPathFactory) -> frozenset[str]:
    """Build the source distribution and return repository-relative archive members."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the packaging content-boundary gate "
            "cannot run without the project's build driver",
        )
    out_dir = tmp_path_factory.mktemp("sdist-out")
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    archives = scan_directory(out_dir, pattern="cadrumo-*.tar.gz")
    if len(archives) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.tar.gz in {out_dir}; got {[p.name for p in archives]!r}")
    with tarfile.open(archives[0], mode="r:gz") as archive:
        return frozenset("/".join(Path(member.name).parts[1:]) for member in archive.getmembers())


def _test_members(members: frozenset[str]) -> list[str]:
    """Return every wheel member that lives under a ``tests`` package."""

    offenders: list[str] = []
    for name in members:
        parts = Path(name).parts
        if any(part == "tests" for part in parts):
            offenders.append(name)
    return sorted(offenders)


def test_wheel_excludes_every_test_member(wheel_members: frozenset[str]) -> None:
    """No file under any ``tests/`` package ships in the wheel."""

    offenders = _test_members(wheel_members)
    assert not offenders, (
        f"the wheel ships {len(offenders)} test member(s) the data-budget exclude should have shed; "
        f"first ten: {offenders[:10]!r}"
    )


def test_distributions_ship_only_the_product_package(
    wheel_members: frozenset[str],
    sdist_members: frozenset[str],
) -> None:
    """Every archive member belongs to the product package or its own build metadata.

    Stated as a closed allowlist rather than a list of excluded repository
    roots. An allowlist cannot fall behind the repository: a new top-level
    directory is refused the moment it reaches an archive, whereas an
    exclusion list only ever refuses the roots someone remembered to name.
    """

    # An installed wheel is the package and the backend's own dist-info; an
    # sdist additionally carries the project files the build configuration
    # declares. Each archive is judged against what IT may ship, never against
    # a shared list that would have to be loosened to the union of both.
    allowed_by_archive = (
        ("wheel", wheel_members, frozenset({_WHEEL_PREFIX}), _wheel_root),
        ("sdist", sdist_members, _declared_sdist_roots() | _BUILD_BACKEND_MEMBERS, _sdist_root),
    )
    for archive_kind, members, allowed_roots, root_of in allowed_by_archive:
        offenders = sorted(member for member in members if Path(member).parts and root_of(member) not in allowed_roots)
        assert not offenders, (
            f"{archive_kind} delivers members the build configuration never declared: {offenders[:10]!r}"
        )


def test_wheel_keeps_required_data_roots(wheel_members: frozenset[str]) -> None:
    """Every functional ``_data`` root still ships after the tests exclude."""

    missing_roots = [
        root
        for root in _REQUIRED_DATA_ROOTS
        if not any(name.startswith(f"{_WHEEL_DATA_PREFIX}/{root}/") for name in wheel_members)
    ]
    assert not missing_roots, (
        f"the wheel is missing required _data root(s) {missing_roots!r}; the tests exclude stripped functional payload"
    )


def test_wheel_keeps_required_functional_members(wheel_members: frozenset[str]) -> None:
    """The py.typed marker, BIP-39 wordlist, and external_constants.toml still ship."""

    missing = sorted(member for member in _REQUIRED_MEMBERS if member not in wheel_members)
    assert not missing, (
        f"the wheel is missing required functional member(s) {missing!r}; the tests exclude stripped functional payload"
    )


def test_wheel_ships_no_corpus_source_binaries(wheel_members: frozenset[str]) -> None:
    """No ``_data/corpus`` pdf/xls/xlsx member survives the wheel-split exclude."""

    offenders = sorted(
        member
        for member in wheel_members
        if member.startswith(_WHEEL_CORPUS_PREFIX) and member.lower().endswith(_CORPUS_BINARY_SUFFIXES)
    )
    assert not offenders, (
        f"the slim wheel ships {len(offenders)} corpus source binary member(s) the wheel-split exclude should have "
        f"shed to the aeat-data-* companions; first ten: {offenders[:10]!r}"
    )


def test_wheel_keeps_corpus_derived_surfaces(wheel_members: frozenset[str]) -> None:
    """The corpus DERIVED surfaces the runtime reads survive the binary exclude.

    The exclude sheds only the source binaries; the extracted text and normative
    html the grounding search and legal gates read at runtime MUST stay, or the
    slim wheel would be functionally broken. Each probe asserts at least one
    member of the surface ships.
    """

    surfaces: dict[str, Callable[[str], bool]] = {
        "corpus extracted text (*.extracted.md)": lambda m: (
            m.startswith(_WHEEL_CORPUS_PREFIX) and m.endswith(".extracted.md")
        ),
        "corpus extracted data (*.extracted.json)": lambda m: (
            m.startswith(_WHEEL_CORPUS_PREFIX) and m.endswith(".extracted.json")
        ),
        "corpus normative html": lambda m: (
            m.startswith(f"{_WHEEL_CORPUS_PREFIX}normatives/html/") and m.endswith(".html")
        ),
    }
    assert wheel_members, "the wheel listed no members; every corpus surface would read as absent or present alike"
    missing = sorted(name for name, pred in surfaces.items() if not any(pred(member) for member in wheel_members))
    assert not missing, (
        f"the wheel is missing corpus derived surface(s) {missing!r}; the corpus-binary exclude over-stripped payload "
        "the runtime reads"
    )


def test_wheel_keeps_registry_payload(wheel_members: frozenset[str]) -> None:
    """Representative registry members still ship."""

    def _count(prefix: str) -> int:
        return sum(1 for member in wheel_members if member.startswith(prefix))

    registry_count = _count(f"{_WHEEL_DATA_PREFIX}/registry/")
    assert registry_count > 0, "the wheel ships no registry members; the split over-stripped the registry payload"
