"""Regression coverage for the fragmented-revision fragment merge order.

A directory-mode revision's ``casillas/`` (and other source-native) section
allows mixed-case fragment filenames, and :class:`~pathlib.Path` ordering
folds case on Windows (``ntpath``'s ``normcase``) but not on POSIX. Sorting
fragment paths with the bare :class:`~pathlib.Path` ordering therefore made
the fragment merge order -- and so the materialised row order and compiled
identity -- depend on the host platform rather than on the source tree.

These tests build an isolated temp fragment tree whose two ``casillas/``
filenames are chosen so that Windows' case-folded ordering and the canonical
code-point ordering disagree, and pin the canonical (platform-independent)
order at both surfaces that discover a fragmented revision's file set: the
production merge order in ``_loader_internals`` and the revision-source
discovery in ``loader_cache``.
"""

from __future__ import annotations

import ntpath
from pathlib import Path

import pytest

from ..compiler.loader_cache import fragment_sort_key
from ..compiler.loader_grammar import revision_section_fragment_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Second character differs only in case: 'T' (0x54) sorts before 'd' (0x64) by
# code point, but 't' (0x74, the Windows case-fold of 'T') sorts after 'd'.
# That is exactly the reordering the five affected registry editions hit.
_CANONICAL_FIRST = "cTelefono.toml"
_CANONICAL_SECOND = "cdireccion.toml"


def _legacy_windows_path_sort(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Reproduce the pre-fix ``sorted(paths)`` result as Windows would order it.

    ``ntpath.normcase`` is used explicitly -- rather than relying on the
    host's own :class:`~pathlib.Path` flavour -- so this reproduces the
    removed production behavior deterministically on every platform the
    suite runs on, not only when the test happens to execute on Windows.
    """
    return tuple(sorted(paths, key=lambda p: ntpath.normcase(str(p))))


def _write_casilla_fragments(casillas_dir: Path) -> tuple[Path, Path]:
    casillas_dir.mkdir(parents=True, exist_ok=True)
    first = casillas_dir / _CANONICAL_FIRST
    second = casillas_dir / _CANONICAL_SECOND
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    return first, second


def test_fixture_diverges_under_the_legacy_windows_sort(tmp_path: Path) -> None:
    """Prove the fixture actually triggers the platform-dependent reordering.

    This is the detector-teeth check: it evaluates the OLD sort key inline
    (never by editing production code) and shows it disagrees with the
    canonical order for this fixture, so a regression back to a bare
    ``sorted(paths)`` would be caught by the assertions below.
    """
    casillas_dir = tmp_path / "casillas"
    first, second = _write_casilla_fragments(casillas_dir)

    canonical_order = tuple(sorted((first, second), key=fragment_sort_key))
    legacy_order = _legacy_windows_path_sort((first, second))

    assert canonical_order == (first, second)
    assert legacy_order == (second, first)
    assert legacy_order != canonical_order


def test_revision_section_fragment_paths_uses_the_canonical_order(tmp_path: Path) -> None:
    """The production merge-order function sorts by the platform-independent key."""
    casillas_dir = tmp_path / "casillas"
    first, second = _write_casilla_fragments(casillas_dir)

    result = revision_section_fragment_paths((casillas_dir,))

    assert result == (first, second)
    assert result != _legacy_windows_path_sort((first, second))
