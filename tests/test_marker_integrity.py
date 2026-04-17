"""AST-backed integrity audit for the nine-marker taxonomy.

Walks every test module under ``src/aeat/`` and ``tests/`` and asserts
that each carries a single top-level ``pytestmark = [...]`` assignment
containing exactly one access marker (``unit`` / ``live_read`` /
``live_write``) and at least one ``domain_*`` marker.

The walker uses :mod:`ast` only; it does not import the test modules.
The file self-validates because the discovery glob includes itself.

See charter ``#116`` and ``tests/README.md`` for the taxonomy contract.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ACCESS_MARKERS = frozenset({"unit", "live_read", "live_write"})


def _discover_test_modules() -> list[Path]:
    """Return every ``test_*.py`` and ``_test_*.py`` module in-scope.

    Excludes ``__init__.py`` files and any module under ``tests/fixtures/``
    (helpers, not test modules). Includes ``src/aeat/**`` and ``tests/**``.
    """
    globs = (
        "src/aeat/**/test_*.py",
        "src/aeat/**/_test_*.py",
        "tests/**/test_*.py",
        "tests/**/_test_*.py",
    )
    collected: set[Path] = set()
    for glob in globs:
        for path in _REPO_ROOT.glob(glob):
            if path.name == "__init__.py":
                continue
            # Skip tests/fixtures/** helper modules (not test modules).
            parts = path.parts
            if "tests" in parts and "fixtures" in parts and parts.index("tests") < parts.index("fixtures"):
                continue
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

    assign_node: ast.Assign | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "pytestmark":
                assign_node = node
                break

    if assign_node is None:
        return set(), "missing top-level `pytestmark = [...]` assignment"

    value = assign_node.value
    if not isinstance(value, ast.List | ast.Tuple):
        return set(), "`pytestmark` must be assigned a list or tuple literal"

    names: set[str] = set()
    for element in value.elts:
        # Accept either `pytest.mark.<name>` (attribute chain, used for
        # access + domain markers) or `pytest.mark.<name>(...)` (call
        # expression, used for conditional markers like
        # `pytest.mark.skipif(cond, reason=...)`). Names from the latter
        # shape are recorded but do not participate in access/domain
        # validation because those are always attribute-chained.
        attr_chain = element.func if isinstance(element, ast.Call) else element
        if not isinstance(attr_chain, ast.Attribute):
            return set(), f"unexpected element type {type(element).__name__} in pytestmark"
        mark_attr = attr_chain.value
        if not isinstance(mark_attr, ast.Attribute) or mark_attr.attr != "mark":
            return set(), "element is not a `pytest.mark.<name>` attribute chain"
        mark_root = mark_attr.value
        if not isinstance(mark_root, ast.Name) or mark_root.id != "pytest":
            return set(), "element is not rooted at `pytest`"
        names.add(attr_chain.attr)

    return names, None


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


def test_discovery_found_modules() -> None:
    """Guardrail: the walker must discover at least one test module."""
    assert _MODULES, "no test modules discovered - glob roots or layout changed"
