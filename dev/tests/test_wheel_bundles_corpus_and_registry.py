"""Prove exact built-wheel parity for runtime data in the source tree.

The corpus-registry packaging contract
relocates both data trees under ``src/cadrumo/_data/`` so the existing
``packages = ["src/cadrumo"]`` hatchling directive carries them inside
the wheel without any force-include declaration. The terminology tree
uses the same shipped-data contract. The wheel-split packaging decision
then excludes the corpus SOURCE binaries
(``_data/corpus/**/*.{pdf,docx,xls,xlsm,xlsx,zip}``)
from the command-bearing ``cadrumo`` wheel. They ship in the two mandatory ``cadrumo-data-*``
companion distributions — while every derived surface the runtime reads
(extracted text, normative html, registry, terminology, agent data) stays.
This test verifies that contract end-to-end by driving the real build pipeline:

1. ``uv build --wheel`` is invoked into a temporary output directory.
2. The resulting wheel archive is opened as a zip.
3. Every repository-visible path under the shipped data tree, except the
   excluded corpus source binaries and tests, is asserted to
   appear in the archive at the corresponding ``cadrumo/_data/<relative-path>``
   prefix.
4. The corpus source binaries are asserted absent from the root wheel; the two
   ``cadrumo-data-*`` companion distributions carry them
   (``test_cadrumo_data_distribution`` proves that side).

No mocks, fakes, or skips. If the worktree is missing the ``uv``
binary the test fails loudly so the locator's bundling guarantee is
never silently lost.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT
from dev.source_tree import repository_files

SRC_CADRUMO = REPO_ROOT / "src" / "cadrumo"

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DATA_ROOT = SRC_CADRUMO / "_data"
_WHEEL_DATA_PREFIX = "cadrumo/_data"

# Corpus source binaries excluded from the command-bearing ``cadrumo`` wheel
# (they ship in the two ``cadrumo-data-*`` companions). A path is an excluded binary
# when it lives under ``_data/corpus/`` and carries one of these suffixes.
# Mirrors the ``tool.hatch.build`` exclude patterns in ``pyproject.toml`` and
# the companion builders' suffix sets (``packaging/*/hatch_build.py``).
_CORPUS_BINARY_SUFFIXES = (".pdf", ".docx", ".xls", ".xlsm", ".xlsx", ".zip")


@cache
def _wheel_exclusion_patterns() -> tuple[str, ...]:
    """Return Hatch's declared non-runtime source patterns once per test run."""

    config = parse_toml((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    raw_patterns = config["tool"]["hatch"]["build"]["targets"]["wheel"].get("exclude", [])
    if not isinstance(raw_patterns, list):
        raise TypeError("Hatch wheel exclusion patterns must be declared as an array")
    patterns: list[str] = []
    for pattern in raw_patterns:
        if not isinstance(pattern, str):
            raise TypeError("Hatch wheel exclusion patterns must be strings")
        patterns.append(pattern)
    return tuple(patterns)


def _wheel_excludes(source_relative: str) -> bool:
    """Whether Hatch declares this repository-relative source path non-runtime.

    This parity gate deliberately reads the build declaration instead of
    reproducing its registry-authoring exclusion.  The wheel is then compared
    with the *declared* runtime data set, so an intentional distribution-boundary
    change is tested through the real archive rather than a second hand-written
    inventory.
    """

    source_path = Path(source_relative)
    for pattern in _wheel_exclusion_patterns():
        if pattern.endswith("/**"):
            directory = pattern.removesuffix("/**")
            if source_relative == directory or source_relative.startswith(f"{directory}/"):
                return True
        elif source_path.match(pattern):
            return True
    return False


def _is_corpus_source_binary(source_relative: str) -> bool:
    """Return True for a ``src/cadrumo/_data/corpus`` path that is an excluded source binary."""

    return source_relative.startswith("src/cadrumo/_data/corpus/") and source_relative.lower().endswith(
        _CORPUS_BINARY_SUFFIXES
    )


def _source_data_files() -> tuple[str, ...]:
    """Return repository-visible files under the runtime data root."""

    files = repository_files(REPO_ROOT, under=("src/cadrumo/_data",))
    if not files:
        raise AssertionError("the source tree contains no runtime data; the packaging contract has regressed")
    return files


def _expected_archive_paths(source_files: tuple[str, ...]) -> set[str]:
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
    (``_data/corpus/**/*.{pdf,docx,xls,xlsm,xlsx,zip}``):
    the wheel-split decision moves them to the two ``cadrumo-data-*`` companions, so
    they are legitimately absent from this slim wheel and must not be expected here.
    """

    prefix = "src/cadrumo/_data/"
    expected: set[str] = set()
    for path in source_files:
        if not path.startswith(prefix):
            raise AssertionError(f"source enumeration returned a path outside src/cadrumo/_data/: {path!r}")
        if _is_corpus_source_binary(path) or _wheel_excludes(path):
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
    wheels = scan_directory(out_dir, pattern="cadrumo-*.whl")
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


def test_wheel_archive_contains_every_runtime_data_file(built_wheel: Path) -> None:
    """The wheel's complete data payload equals the policy-projected source tree."""

    expected = _expected_archive_paths(_source_data_files())
    with zipfile.ZipFile(built_wheel) as archive:
        actual = {
            info.filename
            for info in archive.infolist()
            if not info.is_dir() and info.filename.startswith(f"{_WHEEL_DATA_PREFIX}/")
        }
    # The published authority is GENERATED, not authored: the packaging hook
    # stages it at build time rather than reading it from the checkout, so it
    # has no source counterpart and this source-versus-wheel comparison has
    # nothing to match it against. It is not unchecked -- it carries its own
    # positive invariant in
    # `test_wheel_carries_exactly_one_published_authority_generation`, which is
    # stricter than the subtraction here could be.
    actual = {name for name in actual if not name.startswith(f"{_AUTHORITY_PREFIX}/")}
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    assert not missing and not unexpected, (
        f"wheel data payload differs from source runtime data: missing={missing[:10]!r}, unexpected={unexpected[:10]!r}"
    )


#: The published authority's home inside the wheel. Its two members are
#: GENERATED rather than authored, so they are the only build-staged payload
#: with no source counterpart: the packaging hook stages them at build time
#: instead of reading them from the checkout, which is why a source-versus-wheel
#: comparison counts them as surplus. Every companion hook stages from its own
#: SOURCE tree, so nothing else force-included reaches this gate.
_AUTHORITY_PREFIX = f"{_WHEEL_DATA_PREFIX}/registry/authority"

#: The descriptor naming the one database generation the wheel carries.
_AUTHORITY_DESCRIPTOR = f"{_AUTHORITY_PREFIX}/authority.current.json"

#: A content-addressed authority database. The name IS the SHA-256 of the file,
#: so it changes on every registry edit by construction and may never be pinned
#: as a literal. `_selected_pair` in packaging/authority/hatch_build.py admits
#: exactly this shape, verifies the digest against the bytes, and has never
#: admitted a third file under this prefix.
_AUTHORITY_DATABASE = re.compile(rf"^{re.escape(_AUTHORITY_PREFIX)}/authority-[0-9a-f]{{64}}\.sqlite3$")


def _authority_members(archive: zipfile.ZipFile) -> set[str]:
    """Return every wheel member under the published-authority prefix."""
    return {
        info.filename
        for info in archive.infolist()
        if not info.is_dir() and info.filename.startswith(f"{_AUTHORITY_PREFIX}/")
    }


def authority_findings(members: set[str], descriptor: object) -> list[str]:
    """Return every way this member set violates the one-generation invariant.

    Separated from the live case so the cases below can drive it with a member
    set they construct. A positive assertion that has only ever seen a correct
    wheel is indistinguishable from one that cannot fail.
    """
    findings: list[str] = []
    databases = sorted(name for name in members if _AUTHORITY_DATABASE.match(name))
    if len(databases) != 1:
        findings.append(f"expected exactly one content-addressed authority database, got {databases!r}")
    if _AUTHORITY_DESCRIPTOR not in members:
        findings.append(f"the authority descriptor is missing: {sorted(members)!r}")
    strays = sorted(members - {*databases, _AUTHORITY_DESCRIPTOR})
    if strays:
        findings.append(f"unexpected members under the published-authority prefix: {strays!r}")
    if not isinstance(descriptor, dict):
        findings.append(f"the descriptor is not an object: {descriptor!r}")
        return findings
    named = descriptor.get("database")
    if not isinstance(named, str) or not named:
        findings.append(f"the descriptor names no database: {descriptor!r}")
    elif len(databases) == 1 and not databases[0].endswith(f"/{Path(named).name}"):
        findings.append(f"the descriptor names {named!r} but the wheel carries {databases[0]!r}")
    return findings


def test_wheel_carries_exactly_one_published_authority_generation(built_wheel: Path) -> None:
    """The wheel ships one descriptor and the one database it names.

    A POSITIVE assertion rather than an exemption, and the distinction is the
    whole point. Subtracting this subtree from the source comparison would make
    the gate green -- and blind to whatever else landed here. A superseded
    generation shipped alongside a current one is roughly 80MB of dead payload
    that an exemption waves through and this case refuses.

    The on-disk count and the wheel count are different numbers on purpose.
    ``.authority/`` may legitimately hold two databases: on Windows a superseded
    generation stays leased while a reader holds it open, and retirement returns
    it rather than failing. The build hook never includes the DIRECTORY -- it
    includes the one file the descriptor names -- so the on-disk count varies
    and this one does not.
    """
    with zipfile.ZipFile(built_wheel) as archive:
        members = _authority_members(archive)
        descriptor = json.loads(archive.read(_AUTHORITY_DESCRIPTOR).decode("utf-8"))

    assert members, "the wheel carries no published authority at all"
    assert authority_findings(members, descriptor) == []


def _member_set(*names: str) -> set[str]:
    """Return a member set under the authority prefix, from bare file names."""
    return {f"{_AUTHORITY_PREFIX}/{name}" for name in names}


_A_DIGEST = "a" * 64
_B_DIGEST = "b" * 64


def test_a_second_generation_in_the_wheel_is_reported() -> None:
    """Teeth, and the case an exemption would have waved through.

    Two databases is ~80MB of superseded authority shipped to every user. The
    subtraction form of this fix could not have seen it.
    """
    members = _member_set(f"authority-{_A_DIGEST}.sqlite3", f"authority-{_B_DIGEST}.sqlite3", "authority.current.json")

    findings = authority_findings(members, {"database": f"authority-{_A_DIGEST}.sqlite3"})

    assert len(findings) == 1
    assert "exactly one content-addressed authority database" in findings[0]


def test_a_stray_file_under_the_prefix_is_reported() -> None:
    """Teeth: the invariant is the whole subtree, not just the pair's presence."""
    members = _member_set(f"authority-{_A_DIGEST}.sqlite3", "authority.current.json", "authority.backup.json")

    findings = authority_findings(members, {"database": f"authority-{_A_DIGEST}.sqlite3"})

    assert len(findings) == 1
    assert "unexpected members" in findings[0]


def test_a_descriptor_naming_another_generation_is_reported() -> None:
    """Teeth: shipping a current database beside a stale descriptor."""
    members = _member_set(f"authority-{_A_DIGEST}.sqlite3", "authority.current.json")

    findings = authority_findings(members, {"database": f"authority-{_B_DIGEST}.sqlite3"})

    assert len(findings) == 1
    assert "but the wheel carries" in findings[0]


def test_the_correct_pair_is_accepted() -> None:
    """The positive control: the shape the build actually produces passes."""
    members = _member_set(f"authority-{_A_DIGEST}.sqlite3", "authority.current.json")

    assert authority_findings(members, {"database": f"authority-{_A_DIGEST}.sqlite3"}) == []


def test_wheel_excludes_renta_source_pdfs(built_wheel: Path) -> None:
    """The Renta ``source.pdf`` corpus binaries are absent from the slim wheel.

    They are corpus source binaries under ``corpus/manuals`` and ship in the
    ``cadrumo-data-manuals`` companion, not this wheel; asserting their absence pins
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
        "they belong in the cadrumo-data-manuals companion distribution"
    )


def test_wheel_keeps_renta_page_annotations_beside_extracted_text(built_wheel: Path) -> None:
    """Small semantic selectors stay in the main wheel while their PDFs stay split."""
    expected = {
        f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/2025/part1/source.pdf.annotation.json",
        f"{_WHEEL_DATA_PREFIX}/corpus/manuals/renta/2025/part2-deducciones-autonomicas/source.pdf.annotation.json",
    }
    with zipfile.ZipFile(built_wheel) as archive:
        names = {info.filename for info in archive.infolist()}

    assert expected <= names


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
