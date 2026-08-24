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
(:func:`ast_for_path`, :func:`package_python_files`, and friends), the
committed-justificante parse cache, and the shared typed M303
filing-evidence fixture builder are re-exported here as the canonical
cross-package import surface for other test modules' structural ratchets
and cross-layer fixtures.

The rest of the support modules here -- ``secure_sql``, ``cli_runner``,
``user_profile``, ``registry_observations`` and their two dozen siblings --
are reached by cross-package consumers through their own submodule path
(``from cadrumo.tests.secure_sql import ...``), never through this facade.
That is the deliberate convention of this package, not an oversight waiting
to be swept: the reach spans well over a thousand import sites, across the
better part of a thousand test modules and roughly thirty support modules,
and it is what the tree does uniformly.

The facade-ownership discipline that would otherwise forbid a
submodule-direct reach governs PRODUCTION packages, where a single canonical
public surface per package is what keeps a domain boundary auditable. This
package is wheel-excluded test plumbing consumed only by other tests, and
re-exporting its modules here would invert the cost rather than pay it:
``secure_sql`` alone drags the whole ``adapters.persistence.storage`` stack,
and eagerly binding it would make every module that touches any name on this
facade -- including the domain-free AST and path inventory most consumers
actually want -- import it. The submodule path costs nothing and names its
owner exactly.

The two names in :data:`_LAZY_EXPORTS` are consequently NOT a template.
Each sits on this facade for its own specific reason, stated in
``__getattr__`` below, and each is lazy precisely so it does not drag its
domain surface into an unrelated test's import graph. Two entries are not a
migration in progress: a new shared helper belongs in a submodule, imported
by its path, not promoted to a third row here.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING

from ._bucket_id_fixture import bucket_id
from ._collection_storage_root import (
    apply_collection_storage_root,
    collection_storage_root,
    process_is_live,
    pytest_numbered_dir_root,
    reap_abandoned_numbered_dirs,
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
    modules_declaring_class,
    non_test_package_python_files,
    non_test_python_files_under,
    package_ast_items,
    package_python_files,
    prime_ast_cache,
    production_ast_items,
    production_python_files,
    python_files_under,
    qualified_name,
    repo_path,
    repo_relative,
)
from ._size_budget import (
    CALLABLE_POLICY,
    MIN_SCANNED_CALLABLES,
    MIN_SCANNED_MODULES,
    MODULE_POLICY,
    BudgetPolicy,
    EmptyScanError,
    assert_real_corpus,
    build_limits,
    callable_key,
    evaluate_budget,
    measure_callable_lines,
    measure_module_lines,
    scan_callable_lines,
    scan_module_lines,
)
from ._storage_path_grammar import (
    assert_grammar_vocabulary_is_declared,
    assert_path_matches_grammar,
    literal_directory_runs,
)

if TYPE_CHECKING:
    from ._justificante_parse_cache import parse_committed_justificante_fixture
    from .filing_evidence import general_m303_filing_evidence

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"
"""Root of the on-disk fixture tree bundled with the package."""

__all__ = [
    "CALLABLE_POLICY",
    "FIXTURES_DIR",
    "MIN_SCANNED_CALLABLES",
    "MIN_SCANNED_MODULES",
    "MODULE_POLICY",
    "REPO_ROOT",
    "SRC_CADRUMO",
    "BudgetPolicy",
    "EmptyScanError",
    "aeat_relative",
    "apply_collection_storage_root",
    "assert_grammar_vocabulary_is_declared",
    "assert_path_matches_grammar",
    "assert_real_corpus",
    "ast_for_path",
    "bucket_id",
    "build_limits",
    "callable_key",
    "collection_storage_root",
    "discover_test_control_modules",
    "evaluate_budget",
    "general_m303_filing_evidence",
    "leaf_name",
    "literal_directory_runs",
    "measure_callable_lines",
    "measure_module_lines",
    "module_name",
    "modules_declaring_class",
    "non_test_package_python_files",
    "non_test_python_files_under",
    "package_ast_items",
    "package_python_files",
    "parse_committed_justificante_fixture",
    "prime_ast_cache",
    "process_is_live",
    "production_ast_items",
    "production_python_files",
    "pytest_numbered_dir_root",
    "python_files_under",
    "qualified_name",
    "reap_abandoned_numbered_dirs",
    "register_collection_storage_root_cleanup",
    "repo_path",
    "repo_relative",
    "scan_callable_lines",
    "scan_module_lines",
    "temporary_env",
]


#: Re-exported name -> owning submodule (relative, resolved through
#: :func:`importlib.import_module`). Every row here is a domain-bearing fixture
#: whose import cost the rest of this facade must not pay.
_LAZY_EXPORTS: dict[str, str] = {
    "parse_committed_justificante_fixture": "._justificante_parse_cache",
    "general_m303_filing_evidence": ".filing_evidence",
}


def __getattr__(name: str) -> object:
    """Lazily resolve the domain-bearing fixture names in :data:`_LAZY_EXPORTS`.

    Deferred (not module-level imports) so that reaching any OTHER name on this
    facade -- the pure, domain-free AST/path inventory helpers most consumers
    want -- never drags ``cadrumo.adapters.inbound.justificante`` /
    ``cadrumo.domain.justificante`` (for the justificante parse cache) or the
    registry / IVA / modelos domain surfaces (for the filing-evidence builder)
    into a ``cadrumo.core`` test's import graph. Mirrors the PEP 562 pattern
    :mod:`application.user_profile` already uses for the same reason.
    """
    module_path = _LAZY_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # module_path is resolved from this package's own closed _LAZY_EXPORTS
    # mapping above, never from caller-supplied input.
    return getattr(
        importlib.import_module(module_path, __name__), name
    )  # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
