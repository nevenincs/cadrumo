"""Share the repository-wide locale scans between the cases that read them.

Walking and parsing every product source tree takes about a minute, and a
dozen cases here each repeated that walk to read the same answer. The scans
below are pure functions of the checked-out tree, which no case in this
directory edits; synthetic trees written under a temporary path never match the
repository roots, so they are still scanned afresh by the real scanner.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import pytest

from .. import _ast_scanner
from .._paths import DOCS_SRC_DIR, LOCALE_SOURCE_EXTRA_DIRS, PRODUCT_SOURCE_DIRS, SRC_DIR


def _repository_roots() -> frozenset[Path]:
    return frozenset(
        path.resolve() for path in (SRC_DIR, DOCS_SRC_DIR, *PRODUCT_SOURCE_DIRS, *LOCALE_SOURCE_EXTRA_DIRS)
    )


@pytest.fixture(scope="session", autouse=True)
def _repository_locale_scans_run_once() -> Iterator[None]:
    """Memoize the real scanners over the repository's own roots for this process."""
    known = _repository_roots()
    real_trees = _ast_scanner.scan_source_trees
    real_markers = _ast_scanner.scan_namespace_markers
    trees: dict[tuple[Path, ...], set[str]] = {}
    markers: dict[Path, set[str]] = {}

    def scan_source_trees(roots: Iterable[Path]) -> set[str]:
        resolved = tuple(Path(root).resolve() for root in roots)
        if not all(root in known for root in resolved):
            return real_trees(resolved)
        if resolved not in trees:
            trees[resolved] = real_trees(resolved)
        return set(trees[resolved])

    def scan_namespace_markers(root: Path) -> set[str]:
        resolved = Path(root).resolve()
        if resolved not in known:
            return real_markers(root)
        if resolved not in markers:
            markers[resolved] = real_markers(root)
        return set(markers[resolved])

    patched: tuple[tuple[str, Callable[..., set[str]]], ...] = (
        ("scan_source_trees", scan_source_trees),
        ("scan_namespace_markers", scan_namespace_markers),
    )
    with pytest.MonkeyPatch.context() as patch:
        for name, replacement in patched:
            patch.setattr(_ast_scanner, name, replacement)
        yield
