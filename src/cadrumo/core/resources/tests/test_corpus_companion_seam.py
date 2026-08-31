"""Tests for the corpus-binary resolution seam over the cadrumo_data namespace.

The command-bearing ``cadrumo`` wheel excludes
``_data/corpus/**/*.{pdf,xls,xlsx}``; those binaries ship in TWO mandatory
sub-cap distributions (``cadrumo-data-manuals`` and
``cadrumo-data-official``) that both contribute subtrees to the SAME
``cadrumo_data`` PEP 420 implicit namespace package. :func:`resolve_corpus_binary`
must resolve a corpus binary identically whether it lives under the ``cadrumo`` tree
(full checkout) or under EITHER companion portion of the ``cadrumo_data`` namespace
(installed cohort), because ``importlib.resources.files("cadrumo_data")`` resolves a
``MultiplexedPath`` spanning every installed portion. These tests exercise the
real ``importlib.resources`` behaviour: each companion portion is simulated with
a real temporary namespace package placed on ``sys.path``, never a mock.
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.directory_scan import DirectoryEntryKind, scan_directory
from ....core.resources.bundled_data import bundled_path, resolve_companion_binary, resolve_corpus_binary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[5]

# A corpus-relative path (segments under ``_data``) guaranteed absent from the
# real ``cadrumo`` tree, used to exercise the companion-only resolution path
# without colliding with a shipped binary.
_PROBE_PARTS = (
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_seam_probe",
    "files",
    "companion-seam-probe.xlsx",
)
_PROBE_BYTES = b"companion-seam-probe-bytes\x00\x01\x02"


def _first_bundled_corpus_binary() -> tuple[tuple[str, ...], bytes]:
    """Return (segments-under-_data, bytes) for a real shipped corpus binary."""
    corpus_root = bundled_path("corpus")
    for suffix in (".xlsx", ".xls", ".pdf"):
        for candidate in scan_directory(
            corpus_root, pattern=f"*{suffix}", recursive=True, select=DirectoryEntryKind.FILES
        ):
            if candidate.stat().st_size < 5_000_000:
                relative = candidate.relative_to(corpus_root.parent)
                return tuple(relative.parts), candidate.read_bytes()
    raise AssertionError("no bundled corpus binary found under the cadrumo tree")


@pytest.fixture
def companion_package(tmp_path: Path) -> Iterator[Path]:
    """Install a real temporary ``cadrumo_data`` package on ``sys.path``.

    The package mirrors ``cadrumo/_data`` and carries the probe binary at
    ``cadrumo_data/_data/<_PROBE_PARTS>``. Yields the package root and tears the
    package down from ``sys.path`` / ``sys.modules`` afterwards so it does not
    leak into other tests.
    """
    package_root = tmp_path / "cadrumo_data"
    (package_root / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    probe_path = package_root / "_data" / Path(*_PROBE_PARTS)
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_bytes(_PROBE_BYTES)

    sys.modules.pop("cadrumo_data", None)
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield package_root
    finally:
        sys.modules.pop("cadrumo_data", None)
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        importlib.invalidate_caches()


def test_resolve_corpus_binary_reads_from_the_cadrumo_tree() -> None:
    parts, expected_bytes = _first_bundled_corpus_binary()

    resolved = resolve_corpus_binary(*parts)

    assert resolved is not None
    assert resolved.is_file()
    assert resolved.read_bytes() == expected_bytes


def test_resolve_corpus_binary_reads_from_the_companion_when_absent_from_the_tree(
    companion_package: Path,
) -> None:
    # The probe path is absent from the cadrumo tree, so resolution must fall
    # through to the companion and return the identical bytes.
    assert not (bundled_path("corpus").parent / Path(*_PROBE_PARTS)).is_file()

    resolved = resolve_corpus_binary(*_PROBE_PARTS)

    assert resolved is not None
    assert resolved.is_file()
    assert resolved.read_bytes() == _PROBE_BYTES


def test_resolve_corpus_binary_returns_none_when_absent_from_both_roots() -> None:
    # No companion installed and the probe path is not in the cadrumo tree.
    assert resolve_corpus_binary(*_PROBE_PARTS) is None
    assert resolve_companion_binary(*_PROBE_PARTS) is None


def test_companion_resolution_is_byte_identical_to_a_tree_read(
    companion_package: Path,
) -> None:
    # A tree read and a companion read of the same content resolve to real,
    # readable on-disk paths carrying identical bytes: the installed-cohort and
    # full-checkout reads are uniform.
    tree_parts, tree_bytes = _first_bundled_corpus_binary()
    tree_path = resolve_corpus_binary(*tree_parts)
    companion_path = resolve_corpus_binary(*_PROBE_PARTS)

    assert tree_path is not None and companion_path is not None
    assert tree_path.read_bytes() == tree_bytes
    assert companion_path.read_bytes() == _PROBE_BYTES
    assert companion_path.parent.name == "files"


# Two distinct corpus-relative probes, each guaranteed absent from the real
# ``cadrumo`` tree, one per companion portion. They mirror the split contract:
# ``cadrumo-data-manuals`` owns ``corpus/manuals`` and ``cadrumo-data-official`` owns
# ``corpus/aeat_official``.
_MANUALS_PORTION_PARTS = (
    "corpus",
    "manuals",
    "modelo_seam_probe",
    "manuals-seam-probe.pdf",
)
_MANUALS_PORTION_BYTES = b"manuals-portion-probe\x00\x10"
_OFFICIAL_PORTION_PARTS = (
    "corpus",
    "aeat_official",
    "disenos_registro",
    "modelo_seam_probe",
    "files",
    "official-seam-probe.xlsx",
)
_OFFICIAL_PORTION_BYTES = b"official-portion-probe\x00\x11"


@pytest.fixture
def two_companion_portions(tmp_path: Path) -> Iterator[tuple[Path, Path]]:
    """Install two real ``cadrumo_data`` namespace PORTIONS on ``sys.path``.

    Each portion is a separate directory root carrying a ``cadrumo_data`` package
    with NO ``__init__.py`` (the shipped-wheel invariant), so together they form
    one PEP 420 implicit namespace package that ``importlib.resources.files``
    resolves as a ``MultiplexedPath``. The manuals portion carries only the
    manuals probe; the official portion carries only the official probe. Tears
    both down from ``sys.path`` / ``sys.modules`` afterwards.
    """
    manuals_root = tmp_path / "portion_manuals"
    official_root = tmp_path / "portion_official"
    for root, parts, payload in (
        (manuals_root, _MANUALS_PORTION_PARTS, _MANUALS_PORTION_BYTES),
        (official_root, _OFFICIAL_PORTION_PARTS, _OFFICIAL_PORTION_BYTES),
    ):
        # A namespace portion ships NO __init__.py; only the mirrored _data tree.
        probe_path = root / "cadrumo_data" / "_data" / Path(*parts)
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        probe_path.write_bytes(payload)

    sys.path.insert(0, str(manuals_root))
    sys.path.insert(0, str(official_root))
    importlib.invalidate_caches()
    try:
        yield manuals_root, official_root
    finally:
        sys.modules.pop("cadrumo_data", None)
        for root in (manuals_root, official_root):
            if str(root) in sys.path:
                sys.path.remove(str(root))
        importlib.invalidate_caches()


def test_resolve_corpus_binary_traverses_both_namespace_portions(
    two_companion_portions: tuple[Path, Path],
) -> None:
    # Neither probe exists in the cadrumo tree, and each lives in a DIFFERENT
    # namespace portion. The MultiplexedPath over the two portions must traverse
    # into whichever portion carries the requested binary, so both resolve.
    manuals = resolve_corpus_binary(*_MANUALS_PORTION_PARTS)
    official = resolve_corpus_binary(*_OFFICIAL_PORTION_PARTS)

    assert manuals is not None and manuals.is_file()
    assert manuals.read_bytes() == _MANUALS_PORTION_BYTES
    assert official is not None and official.is_file()
    assert official.read_bytes() == _OFFICIAL_PORTION_BYTES


def test_companion_resolution_spans_portions_without_an_init(
    two_companion_portions: tuple[Path, Path],
) -> None:
    # The namespace package spans both portions even though NEITHER ships an
    # __init__.py: files() returns a MultiplexedPath and resolution reaches each
    # portion's binary. A single-portion install could resolve only its own half.
    manuals_root, official_root = two_companion_portions
    assert not (manuals_root / "cadrumo_data" / "__init__.py").exists()
    assert not (official_root / "cadrumo_data" / "__init__.py").exists()

    assert resolve_companion_binary(*_MANUALS_PORTION_PARTS) is not None
    assert resolve_companion_binary(*_OFFICIAL_PORTION_PARTS) is not None


@pytest.fixture(scope="module")
def built_companion_portions(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[tuple[tuple[str, ...], bytes], ...]]:
    """Build and expose both real companion wheels as separate namespace portions."""
    root = tmp_path_factory.mktemp("cadrumo-companion-wheels")
    uv = shutil.which("uv")
    assert uv is not None, "the real companion-wheel test requires uv on PATH"
    portions: list[Path] = []
    expected: list[tuple[tuple[str, ...], bytes]] = []
    for project_name in ("cadrumo_data_manuals", "cadrumo_data_official"):
        project = _REPO_ROOT / "packaging" / project_name
        wheel_dir = root / f"{project_name}-wheel"
        portion = root / f"{project_name}-portion"
        subprocess.run(  # noqa: S603 - test intentionally invokes the resolved build driver.
            [uv, "build", "--wheel", "--project", str(project), "--out-dir", str(wheel_dir)],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        [wheel] = scan_directory(wheel_dir, pattern="*.whl")
        with zipfile.ZipFile(wheel) as archive:
            members = sorted(
                name
                for name in archive.namelist()
                if name.startswith("cadrumo_data/_data/corpus/") and not name.endswith("/")
            )
            assert members, f"{wheel.name} contains no Cadrumo companion payload"
            member = members[0]
            expected.append((tuple(Path(member).parts[2:]), archive.read(member)))
            archive.extractall(portion)
        portions.append(portion)

    for portion in portions:
        sys.path.insert(0, str(portion))
    sys.modules.pop("cadrumo_data", None)
    importlib.invalidate_caches()
    try:
        yield tuple(expected)
    finally:
        sys.modules.pop("cadrumo_data", None)
        for portion in portions:
            if str(portion) in sys.path:
                sys.path.remove(str(portion))
        importlib.invalidate_caches()
        shutil.rmtree(root)


def test_built_companion_wheels_share_one_readable_namespace(
    built_companion_portions: tuple[tuple[tuple[str, ...], bytes], ...],
) -> None:
    """Production resolution reads byte-exact payloads from both built wheel portions."""
    for parts, expected_bytes in built_companion_portions:
        resolved = resolve_companion_binary(*parts)
        assert resolved is not None
        assert resolved.read_bytes() == expected_bytes
