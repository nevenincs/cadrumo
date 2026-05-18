"""AST-backed integrity audit for the nine-marker taxonomy.

Walks every test module under ``src/aeat/`` and asserts that each
carries a single top-level ``pytestmark = [...]`` assignment containing
exactly one access marker (``unit`` / ``live_read`` / ``live_write``)
and at least one ``domain_*`` marker.

The walker uses :mod:`ast` only; it does not import the test modules.
The file self-validates because the discovery glob includes itself.

See charter ``#116`` and ``src/aeat/tests/README.md`` for the taxonomy
contract.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_AEAT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SRC_AEAT.parents[1]
_FIXTURES_DIR = _SRC_AEAT / "tests" / "fixtures"
_ACCESS_MARKERS = frozenset({"unit", "live_read", "live_write"})
_DOMAIN_MARKERS = frozenset(
    {
        "domain_application",
        "domain_core",
        "domain_export",
        "domain_inbound",
        "domain_model",
        "domain_outbound",
        "domain_persistence",
    }
)
_AUXILIARY_MARKERS = frozenset({"flaky", "fixture_tier_l3"})
_EXPECTED_CONFIGURED_MARKERS = _ACCESS_MARKERS | _DOMAIN_MARKERS | _AUXILIARY_MARKERS


def _discover_test_modules() -> list[Path]:
    """Return every ``test_*.py`` and ``_test_*.py`` module under ``src/aeat/``.

    Excludes ``__init__.py`` and any module beneath
    ``src/aeat/tests/fixtures/`` (those are fixture-generator helpers
    that ship alongside the bundled fixtures, not project test modules).
    """
    globs = ("**/test_*.py", "**/_test_*.py")
    collected: set[Path] = set()
    for glob in globs:
        for path in _SRC_AEAT.glob(glob):
            if path.name == "__init__.py":
                continue
            try:
                path.relative_to(_FIXTURES_DIR)
            except ValueError:
                collected.add(path)
    return sorted(collected)


def _extract_pytestmark_names(path: Path) -> tuple[set[str], str | None]:
    """Parse ``path`` and return the marker-name set declared at module level.

    Args:
        path: Path to the test module.

    Returns:
        A tuple ``(names, error)``. ``names`` contains every name
        extracted from the module-level ``pytestmark`` assignment.
        ``error`` is a human-readable string describing any structural
        problem (missing assignment, wrong shape, etc.), or ``None`` on
        success.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:  # pragma: no cover - defensive
        return set(), f"SyntaxError: {exc}"
    assign_node = _find_pytestmark_assign(tree)
    if assign_node is None:
        return set(), "missing top-level `pytestmark = [...]` assignment"
    value = assign_node.value
    if not isinstance(value, ast.List | ast.Tuple):
        return set(), "`pytestmark` must be assigned a list or tuple literal"
    names: set[str] = set()
    for element in value.elts:
        marker_name, error = _marker_name_from_pytestmark_element(element)
        if error is not None:
            return set(), error
        assert marker_name is not None  # narrowed by error=None branch
        names.add(marker_name)
    return names, None


def _find_pytestmark_assign(tree: ast.Module) -> ast.Assign | None:
    """Return the module-level ``pytestmark = ...`` assignment node, or ``None``."""
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "pytestmark":
            return node
    return None


def _marker_name_from_pytestmark_element(element: ast.expr) -> tuple[str | None, str | None]:
    """Resolve one ``pytestmark`` list/tuple element to its marker name.

    Accepts either ``pytest.mark.<name>`` (attribute chain, used for
    access + domain markers) or ``pytest.mark.<name>(...)`` (call
    expression, used for conditional markers like
    ``pytest.mark.skipif(cond, reason=...)``). Names from the latter
    shape are recorded but do not participate in access/domain
    validation because those are always attribute-chained.

    Returns ``(name, None)`` on success and ``(None, error)`` on any
    structural mismatch so the caller can short-circuit with the same
    error envelope it was emitting inline.
    """
    attr_chain = element.func if isinstance(element, ast.Call) else element
    if not isinstance(attr_chain, ast.Attribute):
        return None, f"unexpected element type {type(element).__name__} in pytestmark"
    mark_attr = attr_chain.value
    if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
        return None, "element is not a `pytest.mark.<name>` attribute chain"
    mark_root = mark_attr.value
    if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
        return None, "element is not rooted at `pytest`"
    return attr_chain.attr, None


def _pytest_mark_name(node: ast.AST) -> str | None:
    """Return the marker name for ``pytest.mark.<name>`` decorators."""
    attr_chain = node.func if isinstance(node, ast.Call) else node
    if not isinstance(attr_chain, ast.Attribute):
        return None
    mark_attr = attr_chain.value
    if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
        return None
    mark_root = mark_attr.value
    if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
        return None
    return attr_chain.attr


def _placement_error(path: Path) -> str | None:
    """Validate that module-level ``pytestmark`` is the first test statement."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            return None
        return f"`pytestmark` must appear before {type(node).__name__} at line {node.lineno}"
    return "missing top-level `pytestmark = [...]` assignment"


def _function_level_marker_violations(path: Path) -> list[str]:
    """Return function/class decorators that misuse access or domain markers."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            name = _pytest_mark_name(decorator)
            if name in _ACCESS_MARKERS or (name is not None and name.startswith("domain_")):
                violations.append(f"{path.relative_to(_REPO_ROOT)}:{decorator.lineno}: @{name}")
    return violations


def _configured_marker_names() -> list[str]:
    """Return marker names declared in ``pyproject.toml``."""
    data = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    marker_rows = data["tool"]["pytest"]["ini_options"]["markers"]
    return [row.split(":", 1)[0] for row in marker_rows]


_MODULES = _discover_test_modules()


@pytest.mark.parametrize(
    "module_path",
    _MODULES,
    ids=[str(p.relative_to(_REPO_ROOT)).replace("\\", "/") for p in _MODULES],
)
def test_module_carries_valid_pytestmark(module_path: Path) -> None:
    """Every test module must declare a valid nine-marker ``pytestmark``."""
    names, error = _extract_pytestmark_names(module_path)
    relative = module_path.relative_to(_REPO_ROOT)
    assert error is None, f"{relative}: {error}"

    access = names & _ACCESS_MARKERS
    assert len(access) == 1, f"{relative}: must carry exactly one of {sorted(_ACCESS_MARKERS)}; found {sorted(access)}"

    domains = {name for name in names if name.startswith("domain_")}
    assert len(domains) >= 1, f"{relative}: must carry at least one `domain_*` marker; found {sorted(names)}"
    assert domains <= _DOMAIN_MARKERS, f"{relative}: unknown domain marker(s) {sorted(domains - _DOMAIN_MARKERS)}"


@pytest.mark.parametrize(
    "module_path",
    _MODULES,
    ids=[str(p.relative_to(_REPO_ROOT)).replace("\\", "/") for p in _MODULES],
)
def test_module_pytestmark_is_first_test_statement(module_path: Path) -> None:
    """The module marker declaration must precede constants, fixtures, and tests."""
    error = _placement_error(module_path)
    assert error is None, f"{module_path.relative_to(_REPO_ROOT)}: {error}"


def test_no_function_level_access_or_domain_markers() -> None:
    """Access and domain markers are module-level only."""
    violations: list[str] = []
    for module_path in _MODULES:
        violations.extend(_function_level_marker_violations(module_path))
    assert not violations, "function-level access/domain markers are forbidden:\n" + "\n".join(violations)


def test_pyproject_marker_registry_is_pruned_and_unique() -> None:
    """Configured markers must be unique and match the active taxonomy."""
    configured = _configured_marker_names()
    duplicates = sorted({name for name in configured if configured.count(name) > 1})
    assert not duplicates, f"duplicate pytest marker declarations: {duplicates}"
    assert set(configured) == _EXPECTED_CONFIGURED_MARKERS


def test_discovery_found_modules() -> None:
    """Guardrail: the walker must discover at least one test module."""
    assert _MODULES, "no test modules discovered - glob roots or layout changed"
