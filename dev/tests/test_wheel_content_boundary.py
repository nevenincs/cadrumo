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

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from dev.source_tree import repository_files, snapshot

from ..core.directory_scan import scan_directory
from .inventory import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WHEEL_PREFIX = "cadrumo"
_WHEEL_DATA_PREFIX = "cadrumo/_data"
_WHEEL_CORPUS_PREFIX = f"{_WHEEL_DATA_PREFIX}/corpus/"
_AUTHORITY_CANDIDATE_ENV = "CADRUMO_AUTHORITY_CANDIDATE_DIR"
_WHEEL_AUTHORITY_PREFIX = f"{_WHEEL_DATA_PREFIX}/registry/authority/"
_WHEEL_AUTHORITY_DESCRIPTOR = f"{_WHEEL_AUTHORITY_PREFIX}authority.current.json"
_WHEEL_AUTHORED_REGISTRY_PREFIX = f"{_WHEEL_DATA_PREFIX}/registry/aeat/"
_WHEEL_PROFILE_SCHEMA = f"{_WHEEL_DATA_PREFIX}/registry/cadrumo/user_profile/schema.toml"
_SDIST_AUTHORITY_PREFIX = "src/cadrumo/_data/registry/authority/"
_SDIST_AUTHORITY_DESCRIPTOR = f"{_SDIST_AUTHORITY_PREFIX}authority.current.json"
_SDIST_AUTHORED_REGISTRY_PREFIX = "src/cadrumo/_data/registry/aeat/"
_SDIST_PROFILE_SCHEMA = "src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml"
_DATABASE_NAME = re.compile(r"authority-[0-9a-f]{64}\.sqlite3")
_DESCRIPTOR_MEMBERS = frozenset({"format", "database", "database_size", "database_sha256", "logical_generation"})
_PROJECT_VERSION = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
_ALLOWED_WHEEL_ROOTS = frozenset({"cadrumo", "cadrumo_harness", f"cadrumo-{_PROJECT_VERSION}.dist-info"})
_ALLOWED_SDIST_FILES = frozenset(
    {
        ".gitignore",
        "CHANGELOG.md",
        "LICENSE",
        "NOTICE",
        "PKG-INFO",
        "PRIVACY.md",
        "README.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
    }
)
_ALLOWED_SDIST_PREFIXES = ("src/cadrumo/", "src/cadrumo_harness/")


def _wheel_root(member: str) -> str:
    """Return a wheel member's exact top-level package or metadata root."""

    return Path(member).parts[0]


def _unexpected_wheel_members(members: frozenset[str]) -> list[str]:
    """Return wheel members outside the fixed product-package policy."""

    return sorted(
        member for member in members if Path(member).parts and _wheel_root(member) not in _ALLOWED_WHEEL_ROOTS
    )


def _unexpected_sdist_members(members: frozenset[str]) -> list[str]:
    """Return sdist members outside the fixed build-source policy."""

    allowed_directories = {prefix.rstrip("/") for prefix in _ALLOWED_SDIST_PREFIXES}
    return sorted(
        member
        for member in members
        if member not in _ALLOWED_SDIST_FILES
        and member not in allowed_directories
        and not member.startswith(_ALLOWED_SDIST_PREFIXES)
    )


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
def candidate_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Snapshot the repository and stage the one release-selected authority candidate."""

    raw_candidate = os.environ.get(_AUTHORITY_CANDIDATE_ENV)
    if raw_candidate:
        candidate = Path(raw_candidate).resolve(strict=True)
        source_root: Path | None = None
    else:
        # After the accepted bytes are promoted, the ordinary archive gate may
        # read the promoted pair directly.  Before promotion, C supplies an
        # isolated candidate directory and this branch must never fall back to
        # the retired JSON frame.
        candidate = REPO_ROOT / "src" / "cadrumo" / "_data" / "registry" / "authority"
        source_root = REPO_ROOT
        if not candidate.is_dir():
            raise AssertionError(f"{_AUTHORITY_CANDIDATE_ENV} must name the validated candidate directory")
    descriptor = candidate / "authority.current.json"
    if not descriptor.is_file():
        raise AssertionError(f"authority candidate has no descriptor: {descriptor}")
    document = json.loads(descriptor.read_text(encoding="utf-8"))
    database_name = document.get("database")
    if not isinstance(database_name, str) or _DATABASE_NAME.fullmatch(database_name) is None:
        raise AssertionError(f"authority candidate has an invalid database name: {database_name!r}")
    database = candidate / database_name
    if database.resolve().parent != candidate:
        raise AssertionError("authority candidate database escapes its directory")
    if not database.is_file():
        raise AssertionError(f"authority candidate has no selected database: {database}")
    database_bytes = database.read_bytes()
    database_digest = hashlib.sha256(database_bytes).hexdigest()
    if database_digest != document.get("database_sha256"):
        raise AssertionError("authority candidate descriptor does not match selected database bytes")
    if len(database_bytes) != document.get("database_size"):
        raise AssertionError("authority candidate descriptor does not match selected database size")
    if source_root is not None:
        return source_root

    parent = tmp_path_factory.mktemp("authority-candidate-source")
    source = parent / "repository"
    snapshot(REPO_ROOT, repository_files(REPO_ROOT), source)
    destination = source / "src" / "cadrumo" / "_data" / "registry" / "authority"
    destination.mkdir(parents=True, exist_ok=True)
    for stale_database in destination.glob("authority-*.sqlite3"):
        if _DATABASE_NAME.fullmatch(stale_database.name):
            stale_database.unlink()
    shutil.copy2(descriptor, destination / descriptor.name)
    shutil.copy2(database, destination / database.name)
    return source


@pytest.fixture(scope="module")
def wheel_archive(candidate_source: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the candidate source snapshot and return its sole wheel."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the packaging content-boundary gate "
            "cannot run without the project's build driver",
        )
    out_dir = tmp_path_factory.mktemp("wheel-out")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir)],
        cwd=candidate_source,
        capture_output=True,
        text=True,
        check=True,
    )
    wheels = scan_directory(out_dir, pattern="cadrumo-*.whl")
    if len(wheels) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.whl in {out_dir}; got {[w.name for w in wheels]!r}")
    return wheels[0]


@pytest.fixture(scope="module")
def wheel_members(wheel_archive: Path) -> frozenset[str]:
    """Return the set of candidate wheel archive member paths."""

    with zipfile.ZipFile(wheel_archive) as archive:
        return frozenset(info.filename for info in archive.infolist())


@pytest.fixture(scope="module")
def sdist_archive(candidate_source: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the candidate source snapshot and return its sole source distribution."""

    if shutil.which("uv") is None:
        raise AssertionError(
            "uv binary not found on PATH; the packaging content-boundary gate "
            "cannot run without the project's build driver",
        )
    out_dir = tmp_path_factory.mktemp("sdist-out")
    subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(out_dir)],
        cwd=candidate_source,
        capture_output=True,
        text=True,
        check=True,
    )
    archives = scan_directory(out_dir, pattern="cadrumo-*.tar.gz")
    if len(archives) != 1:
        raise AssertionError(f"expected exactly one cadrumo-*.tar.gz in {out_dir}; got {[p.name for p in archives]!r}")
    return archives[0]


@pytest.fixture(scope="module")
def sdist_members(sdist_archive: Path) -> frozenset[str]:
    """Return repository-relative members of the built source distribution."""

    with tarfile.open(sdist_archive, mode="r:gz") as archive:
        return frozenset("/".join(Path(member.name).parts[1:]) for member in archive.getmembers())


@pytest.fixture(scope="module")
def rebuilt_wheel_archive(
    sdist_archive: Path, candidate_source: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Build a wheel from the isolated sdist and return its archive path."""

    out_dir = tmp_path_factory.mktemp("sdist-wheel-out")
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(out_dir), str(sdist_archive)],
        cwd=candidate_source,
        capture_output=True,
        text=True,
        check=True,
    )
    wheels = scan_directory(out_dir, pattern="cadrumo-*.whl")
    if len(wheels) != 1:
        raise AssertionError(
            f"expected exactly one rebuilt cadrumo-*.whl in {out_dir}; got {[p.name for p in wheels]!r}"
        )
    return wheels[0]


@pytest.fixture(scope="module")
def rebuilt_wheel_members(rebuilt_wheel_archive: Path) -> frozenset[str]:
    """Return archive members for the wheel rebuilt from the candidate sdist."""

    with zipfile.ZipFile(rebuilt_wheel_archive) as archive:
        return frozenset(info.filename for info in archive.infolist())


def _assert_authority_archive(
    members: frozenset[str],
    *,
    prefix: str,
    descriptor_name: str,
    descriptor: bytes,
    database: bytes,
) -> str:
    """Require one descriptor and its exact content-addressed database member."""

    document = json.loads(descriptor)
    assert isinstance(document, dict)
    assert set(document) == _DESCRIPTOR_MEMBERS
    assert document["format"] == "cadrumo-authority-descriptor-v1"
    database_name = document["database"]
    assert isinstance(database_name, str)
    assert _DATABASE_NAME.fullmatch(database_name)
    database_digest = hashlib.sha256(database).hexdigest()
    assert database_name == f"authority-{database_digest}.sqlite3"
    assert document["database_sha256"] == database_digest
    assert document["database_size"] == len(database)
    assert {member for member in members if member.startswith(prefix) and not member.endswith("/")} == {
        descriptor_name,
        prefix + database_name,
    }
    return database_name


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

    unexpected_by_archive = (
        ("wheel", _unexpected_wheel_members(wheel_members)),
        ("sdist", _unexpected_sdist_members(sdist_members)),
    )
    for archive_kind, offenders in unexpected_by_archive:
        assert not offenders, f"{archive_kind} delivers members outside the fixed product policy: {offenders[:10]!r}"


def test_distribution_allowlist_rejects_policy_widening() -> None:
    """Representative new package and source roots cannot expand the oracle."""

    assert _unexpected_wheel_members(frozenset({"unexpected_product/__init__.py"}))
    assert _unexpected_wheel_members(frozenset({"cadrumo-rogue/payload.txt"}))
    assert _unexpected_wheel_members(frozenset({"cadrumo-rogue.dist-info/payload.txt"}))
    assert _unexpected_wheel_members(frozenset({"cadrumo-9.9.9.dist-info/METADATA"}))
    assert _unexpected_sdist_members(frozenset({"packaging/unexpected_product/pyproject.toml"}))


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


def test_wheel_keeps_registry_payload(wheel_members: frozenset[str], wheel_archive: Path) -> None:
    """The built wheel carries exactly the selected authority pair, never authoring input.

    This is deliberately an archive-level release gate: it exercises Hatch's
    actual selection rules and detects both ways the boundary can regress.  A
    missing digest-verified artifact makes the product unusable, while a retained TOML
    tree would make a future compiler fallback shippable again.
    """

    with zipfile.ZipFile(wheel_archive) as archive:
        descriptor = archive.read(_WHEEL_AUTHORITY_DESCRIPTOR)
        document = json.loads(descriptor)
        database_name = document["database"]
        database = archive.read(_WHEEL_AUTHORITY_PREFIX + database_name)
    _assert_authority_archive(
        wheel_members,
        prefix=_WHEEL_AUTHORITY_PREFIX,
        descriptor_name=_WHEEL_AUTHORITY_DESCRIPTOR,
        descriptor=descriptor,
        database=database,
    )
    assert _WHEEL_AUTHORITY_PREFIX + "authority.json" not in wheel_members
    authored_members = sorted(member for member in wheel_members if member.startswith(_WHEEL_AUTHORED_REGISTRY_PREFIX))
    assert not authored_members, (
        "the built wheel retains registry authoring input(s), which must stay development-only; "
        f"first ten: {authored_members[:10]!r}"
    )
    assert _WHEEL_PROFILE_SCHEMA not in wheel_members


def test_sdist_keeps_only_published_registry_payload(
    sdist_members: frozenset[str],
    sdist_archive: Path,
    rebuilt_wheel_archive: Path,
    rebuilt_wheel_members: frozenset[str],
) -> None:
    """The source archive can rebuild the selected SQLite authority without authored inputs.

    A wheel-only assertion is insufficient: downstream builders start from the
    sdist, so admitting the authored tree there would preserve the exact source
    material needed to recreate a compiler fallback in a rebuilt distribution.
    """

    with tarfile.open(sdist_archive, mode="r:gz") as archive:
        descriptor_member = next(
            member for member in archive.getmembers() if member.name.endswith("/" + _SDIST_AUTHORITY_DESCRIPTOR)
        )
        descriptor_file = archive.extractfile(descriptor_member)
        assert descriptor_file is not None
        descriptor = descriptor_file.read()
        selected = json.loads(descriptor)
        database_member = next(
            member
            for member in archive.getmembers()
            if member.name.endswith("/" + _SDIST_AUTHORITY_PREFIX + selected["database"])
        )
        database_file = archive.extractfile(database_member)
        assert database_file is not None
        database = database_file.read()
    database_name = _assert_authority_archive(
        sdist_members,
        prefix=_SDIST_AUTHORITY_PREFIX,
        descriptor_name=_SDIST_AUTHORITY_DESCRIPTOR,
        descriptor=descriptor,
        database=database,
    )
    assert database_name == selected["database"]
    assert _SDIST_AUTHORITY_PREFIX + "authority.json" not in sdist_members
    authored_members = sorted(member for member in sdist_members if member.startswith(_SDIST_AUTHORED_REGISTRY_PREFIX))
    assert not authored_members, (
        "the built sdist retains registry authoring input(s), which must stay development-only; "
        f"first ten: {authored_members[:10]!r}"
    )
    _assert_authority_archive(
        rebuilt_wheel_members,
        prefix=_WHEEL_AUTHORITY_PREFIX,
        descriptor_name=_WHEEL_AUTHORITY_DESCRIPTOR,
        descriptor=descriptor,
        database=database,
    )
    with zipfile.ZipFile(rebuilt_wheel_archive) as archive:
        assert archive.read(_WHEEL_AUTHORITY_DESCRIPTOR) == descriptor
        assert archive.read(_WHEEL_AUTHORITY_PREFIX + database_name) == database
    assert _WHEEL_AUTHORITY_PREFIX + "authority.json" not in rebuilt_wheel_members
    rebuilt_authored_members = sorted(
        member for member in rebuilt_wheel_members if member.startswith(_WHEEL_AUTHORED_REGISTRY_PREFIX)
    )
    assert not rebuilt_authored_members, (
        "the wheel rebuilt from the sdist retains registry authoring input(s); "
        f"first ten: {rebuilt_authored_members[:10]!r}"
    )
    assert _SDIST_PROFILE_SCHEMA not in sdist_members
    assert _WHEEL_PROFILE_SCHEMA not in rebuilt_wheel_members
    missing_roots = [
        root
        for root in _REQUIRED_DATA_ROOTS
        if not any(name.startswith(f"{_WHEEL_DATA_PREFIX}/{root}/") for name in rebuilt_wheel_members)
    ]
    missing_members = sorted(member for member in _REQUIRED_MEMBERS if member not in rebuilt_wheel_members)
    assert not missing_roots, f"the wheel rebuilt from the sdist is missing required data roots: {missing_roots!r}"
    assert not missing_members, f"the wheel rebuilt from the sdist is missing required members: {missing_members!r}"
