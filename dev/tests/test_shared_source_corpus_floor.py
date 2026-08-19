"""Prove the shared source-AST corpus every ratchet scans is actually populated.

Forty-odd gates take the ``source_tree_ast`` fixture, walk it, and assert their
violation set is empty. Every one of them reports exactly what a correct tree
reports if the fixture ever yields nothing: an empty walk finds no violations,
so a collapsed corpus and a clean codebase are indistinguishable from outside.
Only one consumer asserted the corpus was populated before this module, and it
vouched for its own filtered view rather than the shared substrate.

The fixture can collapse without anyone editing a gate. It is built from
``package_python_files()``, so a moved package root, a widened ``_data``
exclusion, or a read/parse failure sweeping the tree all empty it silently --
and the failure mode is a full green run, which is the worst possible signal.

This module asserts the substrate rather than any one gate's policy. It checks
presence by NAME rather than by count wherever it can: a count drifts with every
added module and invites a floor nobody dares raise, while a named anchor that
disappears is either a real relocation worth noticing or the collapse this
module exists to catch.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Modules that must exist for the package to be the package. Each is a
#: long-lived canonical home rather than a leaf: the config surface, a domain
#: authority, an application service, and the CLI entry. If one of these is
#: genuinely relocated the fix is to re-anchor this list in the same commit --
#: which is exactly the review moment a silent corpus collapse never gets.
_ANCHOR_RELATIVE_PATHS = (
    "core/config.py",
    "core/paths.py",
    "domain/calculations/registry/_schema.py",
    "application/preflight.py",
    "entrypoints/cli/__init__.py",
)

#: Deliberately far below the real population (the package carries thousands of
#: modules). The question this answers is "populated or collapsed", not "how
#: many"; a floor near the true count would fail on any large legitimate
#: refactor and teach the next reader to lower it.
_COLLAPSE_FLOOR = 200


def _relative_paths(corpus: Mapping[Path, ast.AST]) -> set[str]:
    """Return every corpus path relative to the package root, forward-slashed."""
    package_root = REPO_ROOT / "src" / "cadrumo"
    relative: set[str] = set()
    for path in corpus:
        try:
            relative.add(path.resolve().relative_to(package_root).as_posix())
        except ValueError:
            continue
    return relative


def test_the_shared_ast_corpus_is_not_empty(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A gate that walks this corpus must be walking something."""
    assert len(source_tree_ast) > _COLLAPSE_FLOOR, (
        f"the shared source-AST corpus holds {len(source_tree_ast)} modules (floor {_COLLAPSE_FLOOR}); "
        "every ratchet taking this fixture asserts an empty violation set, so a collapsed corpus "
        "makes all of them pass without checking anything"
    )


def test_the_shared_ast_corpus_carries_its_anchors(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Presence by name, so a partial or mis-rooted walk is caught too.

    A count alone cannot distinguish the whole package from some arbitrary
    subtree of it. Naming modules from four different layers means a walk that
    reached only one of them still fails here.
    """
    present = _relative_paths(source_tree_ast)
    missing = sorted(anchor for anchor in _ANCHOR_RELATIVE_PATHS if anchor not in present)
    assert not missing, (
        f"the shared source-AST corpus is missing anchor module(s): {missing}. "
        "Either the walk no longer reaches the whole package, or these were relocated -- "
        "re-anchor this list in the same commit as the move."
    )


def test_the_corpus_excludes_the_data_payload_tree(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """The exclusions the fixture documents must actually hold.

    Stated as a property of the corpus rather than of the walker, so a rewrite
    of the walk that quietly stops excluding the payload tree is caught here.
    Without it the ratchets would scan generated registry data as though it were
    production source.
    """
    leaked = sorted(path for path in _relative_paths(source_tree_ast) if path.startswith("_data/"))
    assert not leaked, (
        f"{len(leaked)} module(s) under the _data payload tree leaked into the shared corpus, "
        f"e.g. {leaked[:5]}; ratchets would scan generated data as production source"
    )


#: Test modules that must be in any honest test-control corpus. Spread across
#: both trees the corpus unions (``dev/`` and ``src/cadrumo/``) so a walk that
#: reached only one of them still fails.
_TEST_CONTROL_ANCHORS = (
    "src/cadrumo/tests/test_config.py",
    "src/cadrumo/tests/test_marker_integrity.py",
    "dev/audit/tests/test_checkout_drift.py",
)

#: Far below the real population, for the same reason as the AST floor above.
_TEST_CONTROL_FLOOR = 100


def _repo_relative(paths: Iterable[Path]) -> set[str]:
    """Return repo-relative forward-slashed paths for a corpus of absolute paths."""
    repo_root = REPO_ROOT
    relative: set[str] = set()
    for path in paths:
        try:
            relative.add(Path(path).resolve().relative_to(repo_root).as_posix())
        except ValueError:
            continue
    return relative


def test_the_test_control_corpus_is_not_empty() -> None:
    """Six ratchets walk this corpus and assert their violation set is empty.

    ``all_test_control_modules()`` unions two discovery passes. If either
    stopped yielding -- a moved tree, a changed suffix filter -- the union can
    empty without any gate changing, and every ratchet over it reports the same
    clean result it reports today. Only one consumer asserted it was populated
    before this.
    """
    from ._project_inventory import all_test_control_modules

    corpus = all_test_control_modules()
    assert len(corpus) > _TEST_CONTROL_FLOOR, (
        f"the test-control corpus holds {len(corpus)} modules (floor {_TEST_CONTROL_FLOOR}); "
        "the broad-exception, monkeypatch and mock ratchets all walk it, so a collapsed "
        "corpus makes every one of them pass without reading anything"
    )


def test_the_test_control_corpus_reaches_both_trees() -> None:
    """A union that lost one of its two halves still looks populated by count."""
    from ._project_inventory import all_test_control_modules

    present = _repo_relative(all_test_control_modules())
    missing = sorted(anchor for anchor in _TEST_CONTROL_ANCHORS if anchor not in present)
    assert not missing, (
        f"the test-control corpus is missing anchor module(s): {missing}. "
        "Either one half of the union stopped yielding, or these moved -- "
        "re-anchor this list in the same commit as the move."
    )
