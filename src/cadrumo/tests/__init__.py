"""Project-bundled test plumbing, meta tests, and fixtures.

This subpackage provides cross-cutting test plumbing for package-root and
project-structure validation across the repository. It
hosts the pytest collection hook (``_marker_hook``), the dotenv loader
the hook uses (``_env_loader``), repo-meta tests (release config,
``.env`` alignment, marker-taxonomy integrity), and the on-disk
``fixtures/`` tree consumed by colocated tests across the package.

Colocated unit tests live next to the modules they exercise (rust-style
``src/cadrumo/<subpkg>/test_*.py``); only repo-meta and fixture-bearing
content lives here. The shared source-inventory helpers
(:func:`ast_for_path`, :func:`package_python_files`, and friends) and the
committed-justificante parse cache are re-exported here as the canonical
cross-package import surface for other test modules' structural ratchets.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ._collection_storage_root import (
    apply_collection_storage_root,
    collection_storage_root,
    register_collection_storage_root_cleanup,
)
from ._env import temporary_env
from ._inventory import (
    REPO_ROOT,
    SRC_CADRUMO,
    aeat_relative,
    ast_for_path,
    discover_test_control_modules,
    leaf_name,
    module_name,
    non_test_package_python_files,
    non_test_python_files_under,
    package_ast_items,
    package_python_files,
    prime_ast_cache,
    production_ast_items,
    production_python_files,
    qualified_name,
    repo_path,
    repo_relative,
)
from ._size_budget import (
    CALLABLE_POLICY,
    MIN_SCANNED_CALLABLES,
    MIN_SCANNED_MODULES,
    MODULE_POLICY,
    SIZE_BUDGET_BASELINE_PATH,
    BudgetPolicy,
    EmptyScanError,
    SizeBudgetBaseline,
    assert_real_corpus,
    build_limits,
    callable_key,
    evaluate_budget,
    load_size_budget_baseline,
    measure_callable_lines,
    measure_module_lines,
    scan_callable_lines,
    scan_module_lines,
    write_size_budget_baseline,
)
from .mcp_session import connected_server_and_client_session

if TYPE_CHECKING:
    from ._justificante_parse_cache import parse_committed_justificante_fixture

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"
"""Root of the on-disk fixture tree bundled with the package."""

__all__ = [
    "CALLABLE_POLICY",
    "FIXTURES_DIR",
    "MIN_SCANNED_CALLABLES",
    "MIN_SCANNED_MODULES",
    "MODULE_POLICY",
    "REPO_ROOT",
    "SIZE_BUDGET_BASELINE_PATH",
    "SRC_CADRUMO",
    "BudgetPolicy",
    "EmptyScanError",
    "SizeBudgetBaseline",
    "aeat_relative",
    "apply_collection_storage_root",
    "assert_real_corpus",
    "ast_for_path",
    "build_limits",
    "callable_key",
    "collection_storage_root",
    "connected_server_and_client_session",
    "discover_test_control_modules",
    "evaluate_budget",
    "leaf_name",
    "load_size_budget_baseline",
    "measure_callable_lines",
    "measure_module_lines",
    "module_name",
    "non_test_package_python_files",
    "non_test_python_files_under",
    "package_ast_items",
    "package_python_files",
    "parse_committed_justificante_fixture",
    "prime_ast_cache",
    "production_ast_items",
    "production_python_files",
    "qualified_name",
    "register_collection_storage_root_cleanup",
    "repo_path",
    "repo_relative",
    "scan_callable_lines",
    "scan_module_lines",
    "temporary_env",
    "write_size_budget_baseline",
]


def __getattr__(name: str) -> object:
    """Lazily resolve ``parse_committed_justificante_fixture``.

    Deferred (not a module-level import) so that reaching any OTHER name on
    this facade -- the pure, domain-free AST/path inventory helpers most
    consumers want -- never drags ``cadrumo.adapters.inbound.justificante`` /
    ``cadrumo.domain.justificante`` into a ``cadrumo.core`` test's import graph.
    Mirrors the PEP 562 pattern :mod:`application.user_profile` already uses
    for the same reason.
    """
    if name == "parse_committed_justificante_fixture":
        import importlib

        module = importlib.import_module("cadrumo.tests._justificante_parse_cache")
        return module.parse_committed_justificante_fixture
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
