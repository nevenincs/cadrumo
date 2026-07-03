"""Tests for the corpus-binary resolution seam over the aeat_data companion.

The slim ``aeat`` runtime wheel excludes ``_data/corpus/**/*.{pdf,xls,xlsx}``;
an optional ``aeat_data`` companion distribution ships exactly those binaries
under mirrored paths. :func:`resolve_corpus_binary` must resolve a corpus binary
identically whether it lives under the ``aeat`` tree (full checkout) or the
``aeat_data`` companion root (split install). These tests exercise the real
``importlib.resources`` behaviour: the companion is simulated with a real
temporary package placed on ``sys.path``, never a mock.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core.resources import (
    bundled_path,
    resolve_companion_binary,
    resolve_corpus_binary,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A corpus-relative path (segments under ``_data``) guaranteed absent from the
# real ``aeat`` tree, used to exercise the companion-only resolution path
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
        for candidate in sorted(corpus_root.rglob(f"*{suffix}")):
            if candidate.is_file() and candidate.stat().st_size < 5_000_000:
                relative = candidate.relative_to(corpus_root.parent)
                return tuple(relative.parts), candidate.read_bytes()
    raise AssertionError("no bundled corpus binary found under the aeat tree")


@pytest.fixture
def companion_package(tmp_path: Path) -> Iterator[Path]:
    """Install a real temporary ``aeat_data`` package on ``sys.path``.

    The package mirrors ``aeat/_data`` and carries the probe binary at
    ``aeat_data/_data/<_PROBE_PARTS>``. Yields the package root and tears the
    package down from ``sys.path`` / ``sys.modules`` afterwards so it does not
    leak into other tests.
    """
    package_root = tmp_path / "aeat_data"
    (package_root / "__init__.py").parent.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    probe_path = package_root / "_data" / Path(*_PROBE_PARTS)
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    probe_path.write_bytes(_PROBE_BYTES)

    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield package_root
    finally:
        sys.modules.pop("aeat_data", None)
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        importlib.invalidate_caches()


def test_resolve_corpus_binary_reads_from_the_aeat_tree() -> None:
    parts, expected_bytes = _first_bundled_corpus_binary()

    resolved = resolve_corpus_binary(*parts)

    assert resolved is not None
    assert resolved.is_file()
    assert resolved.read_bytes() == expected_bytes


def test_resolve_corpus_binary_reads_from_the_companion_when_absent_from_the_tree(
    companion_package: Path,
) -> None:
    # The probe path is absent from the aeat tree, so resolution must fall
    # through to the companion and return the identical bytes.
    assert not (bundled_path("corpus").parent / Path(*_PROBE_PARTS)).is_file()

    resolved = resolve_corpus_binary(*_PROBE_PARTS)

    assert resolved is not None
    assert resolved.is_file()
    assert resolved.read_bytes() == _PROBE_BYTES


def test_resolve_corpus_binary_returns_none_when_absent_from_both_roots() -> None:
    # No companion installed and the probe path is not in the aeat tree.
    assert resolve_corpus_binary(*_PROBE_PARTS) is None
    assert resolve_companion_binary(*_PROBE_PARTS) is None


def test_companion_resolution_is_byte_identical_to_a_tree_read(
    companion_package: Path,
) -> None:
    # A tree read and a companion read of the same content resolve to real,
    # readable on-disk paths carrying identical bytes: the split-install and
    # full-checkout reads are uniform.
    tree_parts, tree_bytes = _first_bundled_corpus_binary()
    tree_path = resolve_corpus_binary(*tree_parts)
    companion_path = resolve_corpus_binary(*_PROBE_PARTS)

    assert tree_path is not None and companion_path is not None
    assert tree_path.read_bytes() == tree_bytes
    assert companion_path.read_bytes() == _PROBE_BYTES
    assert companion_path.parent.name == "files"
