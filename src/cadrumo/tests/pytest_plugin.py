"""Core-only pytest fixtures shared across the repository.

This module is test support, excluded from published wheels. Repository-root
pytest host fixtures that compose application adapters live in the root
conftest, outside the shipped package boundary.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def source_tree_ast() -> Mapping[Path, ast.AST]:
    """Return a module-lifetime mapping of ``src/cadrumo/`` files to their ASTs.

    Covers the package files outside ``__pycache__`` and the ``_data/`` payload
    tree, each read as UTF-8 with ``errors='replace'`` (so a stray encoding
    cookie cannot raise). Files that fail to parse with ``SyntaxError`` are not
    members -- the fixture is a cache, not a syntax gate; ratchets that need to
    surface unparseable files should fall back to their own per-test scan.

    Each module is parsed on first access, through the same process-level
    cache :func:`~cadrumo.tests.inventory.ast_for_path` reads, so a ratchet
    that never threads this fixture through its helpers still shares the parse.
    Parsing lazily is what lets a package-scoped gate run without first paying
    for every other module in the tree.

    Candidate discovery shares the source caches' module lifetime, so the next
    gate discovers additions and removals instead of reusing a stale session
    list. Sources must remain stable during each gate's own module.

    Consumers retain their own filter predicates (e.g. ``test_*.py``
    only, or exclude certain subdirs). The fixture is the AST cache;
    the policy is per-test.
    """
    # Imported here, not at module scope: this module's imports must stay below the
    # storage-root env assignment above, and a function-local import keeps that
    # ordering constraint off the module surface entirely.
    from .inventory import LazySourceTreeAst, package_python_files

    return LazySourceTreeAst(package_python_files())


@pytest.fixture(scope="module", autouse=True)
def _release_the_source_scan_caches_with_their_module() -> Iterator[None]:
    """Free the shared source-parse caches once the module that filled them ends.

    One parse per file, shared across a gate's own tests, is what keeps a
    tree-wide structural ratchet fast. Held for the whole process it also never
    shrank. Sampled per worker over this suite at eight workers: every worker
    settled at about 1.0 GB after collection and then climbed monotonically to
    between 2.1 and 3.5 GB, 23.1 GB in total, and the eleven steepest rises were
    each one tree-walking gate module -- up to 1.33 GB apiece, none of it ever
    returned. A host that has to hold all of it at once is the one that kills a
    worker mid-run, which reads as an unattributable crash in an unrelated test.

    The module boundary is the natural lifetime: file-grouped distribution runs
    every test of a gate consecutively, so the cache is hot exactly while its
    owner needs it and the next module starts from the files it reads itself.
    """
    yield
    from .inventory import release_parsed_sources

    release_parsed_sources()
