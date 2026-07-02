"""Project-bundled test plumbing, meta tests, and fixtures.

This subpackage ships with ``aeat`` so the wheel is self-testable. It
hosts the pytest collection hook (``_marker_hook``), the dotenv loader
the hook uses (``_env_loader``), repo-meta tests (release config,
``.env`` alignment, marker-taxonomy integrity), and the on-disk
``fixtures/`` tree consumed by colocated tests across the package.

Colocated unit tests live next to the modules they exercise (rust-style
``src/aeat/<subpkg>/test_*.py``); only repo-meta and fixture-bearing
content lives here. The shared source-inventory helpers
(:func:`ast_for_path`, :func:`package_python_files`, and friends) and the
committed-justificante parse cache are re-exported here as the canonical
cross-package import surface for other test modules' structural ratchets.
"""

from __future__ import annotations

from pathlib import Path

from ._env import temporary_env
from ._inventory import (
    REPO_ROOT,
    SRC_AEAT,
    ast_for_path,
    leaf_name,
    non_test_package_python_files,
    non_test_python_files_under,
    package_ast_items,
    package_python_files,
    qualified_name,
    repo_path,
    repo_relative,
)
from ._justificante_parse_cache import parse_committed_justificante_fixture

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"
"""Root of the on-disk fixture tree bundled with the package."""

__all__ = [
    "FIXTURES_DIR",
    "REPO_ROOT",
    "SRC_AEAT",
    "ast_for_path",
    "leaf_name",
    "non_test_package_python_files",
    "non_test_python_files_under",
    "package_ast_items",
    "package_python_files",
    "parse_committed_justificante_fixture",
    "qualified_name",
    "repo_path",
    "repo_relative",
    "temporary_env",
]
