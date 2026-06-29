"""Audit gate: every production module is reachable from a test.

Walks the static import graph rooted at every `test_*.py` /
`conftest.py` under `src/aeat/`, resolves relative imports to absolute
`aeat.*` dotted paths, and computes the transitive closure of
production modules reachable from any test. A production module is
considered covered if it sits inside that closure — either directly
imported by a test or transitively through an aggregator `__init__.py`,
a sibling helper, or any other static dependency chain.

The gate fails when a new production module is added that no test
transitively reaches. There is no allowlist: every gap is either
covered by authoring a real-behavior test, by routing the module
through an existing covered aggregator, or by adding the file to
the narrow `_EXEMPTIONS` set with a one-line domain rationale.

Exemption criteria (always excluded from the requirement):
  - `__init__.py` files (package roots; covered transitively)
  - `conftest.py` (pytest configuration; not production logic)
  - Modules named `fixtures.py` or `_fixtures.py` (test-support only)
  - Modules under `__pycache__` directories
  - `test_*.py` files themselves

Limitations: the walker only follows static `import` / `from ... import`
statements. Dynamic imports (`importlib.import_module` on a runtime-
built string) are invisible to the walker; modules loaded only through
dynamic dispatch must either be reachable through some other static
path or carry an explicit `test_*.py` file alongside.
"""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, ast_for_path, module_name, package_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT

# Modules exempted from the pairing requirement.  Each entry is a
# POSIX path relative to PROJECT_ROOT.  Add a one-line justification
# comment for each.
_EXEMPTIONS: frozenset[str] = frozenset(
    {
        # Package __init__ files are tested transitively through their submodules.
        # Fixtures / conftest modules are test-support infrastructure.
        # _playwright.py requires a running browser; browser integration tests
        # live in a separate live-test suite.
        "src/aeat/adapters/outbound/aeat/_playwright.py",
        # Locale scaffold tooling; exercised via CLI integration tests.
        "src/aeat/locales/scaffold.py",
        # Typer subcommand modules registered via _lazy(...) in
        # entrypoints/cli/__init__.py (importlib.import_module on a
        # string arg); the AST walker cannot follow dynamic dispatch.
        # Each is exercised end-to-end via the CLI surface tests under
        # entrypoints/cli/test_*.py that invoke `aeat app <verb> ...`.
        "src/aeat/entrypoints/cli/_exit_codes.py",
        "src/aeat/entrypoints/cli/_registry_corpus.py",
        "src/aeat/entrypoints/cli/_review.py",
        "src/aeat/entrypoints/cli/registry.py",
        # Registry payload modules are imported by CLI/schema registration
        # paths that are exercised by docs-tool conformance gates outside the
        # production package. They must not be pulled into coverage only by a
        # production-embedded documentation generator.
        "src/aeat/entrypoints/cli/_registry_corpus_payloads.py",
        "src/aeat/entrypoints/cli/_registry_payloads.py",
        # `python -m` entry point; not pytest-importable surface.
        # locales/__main__ dispatches into locales/scaffold.py.
        "src/aeat/locales/__main__.py",
    },
)

# `COVERAGE_GAPS` allowlist retired 2026-06-01: the AST import-graph
# helper below proves transitive coverage for every entry that used to
# live here (62 of 66 reach via aggregator __init__.py imports; the
# remaining 4 — reconciliation errors + 3 fixture generators — now
# have dedicated test_*.py files). No allowlist remains.


def _is_exempt(rel: str) -> bool:
    """Return True if ``rel`` is exempted from the coverage requirement."""
    if rel in _EXEMPTIONS:
        return True
    parts = Path(rel).parts
    name = parts[-1] if parts else ""
    if name in {"__init__.py", "conftest.py", "fixtures.py", "_fixtures.py"}:
        return True
    if "__pycache__" in parts:
        return True
    return False


def _collect_production_modules() -> list[Path]:
    """Return every non-test, non-exempt Python module under src/aeat/."""
    return [
        p
        for p in package_python_files(include_data=True)
        if not p.name.startswith("test_") and "__pycache__" not in p.parts and not _is_exempt(repo_relative(p))
    ]


# ---------------------------------------------------------------------------
# Import-graph coverage helper — the canonical gate.
# ---------------------------------------------------------------------------


_AEAT_PACKAGE = "aeat"


def _module_path_for_dotted(dotted: str) -> Path | None:
    """Return the on-disk file for an ``aeat.*`` dotted module name.

    Resolves to either ``<rel>.py`` or ``<rel>/__init__.py`` if either
    exists; returns ``None`` for names that do not map to a real file
    (e.g. ``from .foo import bar`` where ``bar`` is a re-exported name
    in ``foo``'s namespace and not a submodule).
    """
    if not dotted.startswith(_AEAT_PACKAGE):
        return None
    parts = dotted.split(".")
    base = _SRC_ROOT.parent  # src/
    candidate_module = base.joinpath(*parts).with_suffix(".py")
    if candidate_module.is_file():
        return candidate_module
    candidate_package = base.joinpath(*parts, "__init__.py")
    if candidate_package.is_file():
        return candidate_package
    return None


def _file_to_dotted(file_path: Path) -> str:
    """Convert a file under ``src/aeat/`` to its dotted module name."""
    return module_name(file_path)


def _resolve_relative(current_dotted: str, level: int, module: str | None) -> str | None:
    """Resolve a relative-import target to an absolute dotted name.

    ``current_dotted`` is the dotted name of the file containing the
    ``from ... import`` statement (e.g. ``aeat.domain.portals._registry``).
    ``level`` is the number of leading dots in the relative import.
    ``module`` is the module name after the dots, or ``None`` for
    ``from . import x``.
    """
    if level == 0:
        return module
    parts = current_dotted.split(".")
    # __init__-style files are represented without the trailing __init__,
    # so the file at aeat.domain.portals (init) treats `.foo` as
    # aeat.domain.portals.foo. A submodule file like
    # aeat.domain.portals._registry treats `.foo` as
    # aeat.domain.portals.foo (level=1 strips _registry).
    init_path = _SRC_ROOT.parent.joinpath(*parts, "__init__.py")
    is_init = init_path.is_file()
    if is_init:
        # `current_dotted` is the package; level 1 stays in the same package.
        ancestor = parts[: len(parts) - (level - 1)] if level > 0 else parts
    else:
        # `current_dotted` is a module file; level 1 means the parent package.
        ancestor = parts[: len(parts) - level]
    if not ancestor:
        return None
    if module:
        return ".".join([*ancestor, module])
    return ".".join(ancestor)


def _aeat_imports_in(file_path: Path, source_tree_ast: Mapping[Path, ast.AST] | None = None) -> set[str]:
    """Return absolute ``aeat.*`` dotted names imported by ``file_path``.

    For ``from X import Y, Z`` the returned set includes ``X``, ``X.Y``,
    and ``X.Z``; the caller resolves each candidate to a file via
    :func:`_module_path_for_dotted` and silently drops non-module names.
    """
    tree = ast_for_path(file_path, source_tree_ast)
    if tree is None:
        return set()

    current_dotted = _file_to_dotted(file_path)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_AEAT_PACKAGE):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_relative(current_dotted, node.level, node.module)
            if base is None or not base.startswith(_AEAT_PACKAGE):
                continue
            found.add(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                found.add(f"{base}.{alias.name}")
    return found


def _collect_test_entrypoints() -> list[Path]:
    """Return every ``test_*.py`` and ``conftest.py`` under ``src/aeat/``."""
    return [
        p
        for p in package_python_files(include_data=True)
        if "__pycache__" not in p.parts and (p.name.startswith("test_") or p.name == "conftest.py")
    ]


def _transitively_reachable_from_tests(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> set[Path]:
    """Return the set of production module paths reachable from any test.

    The closure starts at every test/conftest entrypoint, follows static
    ``aeat.*`` imports, and stops when no new on-disk module is added.
    Returned paths are absolute and may include both ``foo.py`` modules
    and ``foo/__init__.py`` package roots.
    """
    seen: set[Path] = set()
    queue: deque[Path] = deque(_collect_test_entrypoints())
    while queue:
        current = queue.popleft()
        for dotted in _aeat_imports_in(current, source_tree_ast):
            target = _module_path_for_dotted(dotted)
            if target is None or target in seen:
                continue
            seen.add(target)
            queue.append(target)
    return seen


@cache
def _cached_transitively_reachable_from_tests() -> set[Path]:
    """Return the no-argument import closure once per test process."""
    return _transitively_reachable_from_tests()


def _has_import_graph_coverage(module: Path, reachable: set[Path]) -> bool:
    """Return True if ``module`` is in the test-rooted import closure.

    Package ``__init__.py`` files are considered covered when any module
    under the same package is reachable; the package always imports as a
    side-effect of its submodules being touched.
    """
    if module in reachable:
        return True
    if module.name == "__init__.py":
        package_root = module.parent
        return any(package_root in p.parents for p in reachable)
    return False


def test_import_graph_helper_recognises_aggregator_pattern() -> None:
    """Positive control: portal entries are covered via _registry aggregator."""
    reachable = _cached_transitively_reachable_from_tests()
    # _registry.py imports every portal entry; test_registry.py imports
    # _registry. The closure must therefore include at least one of the
    # portal entry files even though no test_*.py sits next to them.
    portal_entries_dir = _SRC_ROOT / "domain" / "portals" / "_entries"
    portal_modules = [p for p in portal_entries_dir.glob("portal_*.py") if not p.name.startswith("test_")]
    assert portal_modules, "expected portal_*.py entries to exist"
    reached = [p for p in portal_modules if p in reachable]
    assert reached, (
        "import-graph helper failed to reach any portal entry via aeat.domain.portals._registry aggregator imports"
    )


def test_import_graph_helper_skips_orphan_modules() -> None:
    """Negative control: a synthetic dotted name with no file resolves to None."""
    assert _module_path_for_dotted("aeat.does.not.exist.module") is None
    # And a non-aeat dotted name is never resolved.
    assert _module_path_for_dotted("os.path") is None


def test_every_production_module_is_reachable_from_a_test() -> None:
    """Canonical coverage gate. No allowlist.

    Every production module under ``src/aeat/`` (minus the narrow
    ``_EXEMPTIONS`` set) must be statically reachable from at least
    one ``test_*.py`` / ``conftest.py`` entrypoint through the import
    graph. Reachable means the AST walker rooted at any test file
    transitively imports the module — directly, via a sibling
    aggregator, via the package ``__init__.py``, or via any chain of
    static ``import`` / ``from ... import`` statements.

    The gate fails loudly when a new module is added that no test
    transitively reaches. The fix is one of:

    1. Author a real-behavior test next to the module (creates a new
       test_*.py entrypoint that imports the module).
    2. Re-export the module's public surface through a sibling
       aggregator that an existing test already imports.
    3. (Last resort) Add the module to ``_EXEMPTIONS`` with a one-line
       domain rationale comment.

    Per ``test-quality is a review gate`` memory: do NOT author a
    tautological test just to silence this gate. The point is real
    behavior coverage, not gate green-ness.
    """
    production_modules = _collect_production_modules()
    reachable = _cached_transitively_reachable_from_tests()
    gaps: list[str] = []
    for module in production_modules:
        if _has_import_graph_coverage(module, reachable):
            continue
        gaps.append(repo_relative(module))

    assert not gaps, (
        f"Coverage gaps detected ({len(gaps)} modules).\n"
        "These production modules are not reachable through the static\n"
        "import graph from any test entrypoint. Either author a real-\n"
        "behavior test, route the module through an existing covered\n"
        "aggregator, or exempt it in _EXEMPTIONS with a rationale.\n\n" + "\n".join(f"  {g}" for g in sorted(gaps))
    )
