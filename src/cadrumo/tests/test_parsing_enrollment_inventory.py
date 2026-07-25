"""Inventory test: zero inline date.fromisoformat() and value.lower() == "true" survive in production.

Rule
----
Production modules under ``src/cadrumo/`` must not contain:

1. ``date.fromisoformat(`` — invocations bypassing the canonical
   ``_parse_iso8601_date`` or ``_parse_ddmmyyyy_date`` helpers, under *any*
   local spelling. Detection resolves each call's callee through the module's
   own import bindings, so an import alias cannot hide the call: the earlier
   spelling-matched check demanded a literal ``date.fromisoformat`` callee and
   therefore reported green over a real ``_date.fromisoformat`` call site
   reached through ``from datetime import date as _date``.
2. ``value.lower() == "true"`` or ``value.lower() == "false"`` — inline boolean
   parsing that bypasses the canonical ``_parse_bool`` helper.

Exclusions
----------
- ``test_*.py`` files: test suites verify the helpers and may use direct calls.
- ``src/cadrumo/core/parsing/_dates.py``: the canonical implementation itself.
- ``src/cadrumo/core/parsing/_utils.py``: the canonical bool-parsing implementation.

See Also:
    :mod:`~tests._inventory`
        Provides the shared production AST inventory used by this parsing
        enrollment gate.
    :func:`~core.parsing.parse_iso8601_date`
        Public ISO date parser that production callers should use instead of
        direct ``date.fromisoformat`` calls.
    :func:`~core.parsing.parse_ddmmyyyy_date`
        Public Spanish day-first parser for Sede and form-input dates.
    :func:`~core.parsing.parse_bool`
        Public boolean-token parser that replaces inline lower-case string
        comparisons.

Date, day-first, and boolean parsing must funnel through one canonical helper
each, so a locale or format quirk is fixed in exactly one place.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ._inventory import (
    SRC_CADRUMO,
    import_binding_map,
    production_ast_items,
    qualified_name,
    repo_relative,
    resolve_dotted_origin,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_CADRUMO

# Canonical modules that are allowed to use these primitives directly.
_CANONICAL_MODULES: frozenset[str] = frozenset(
    {
        "_dates.py",
        "_utils.py",
    },
)


def _is_excluded(path: Path) -> bool:
    # The canonical implementation modules are exempted by definition.
    if path.name in _CANONICAL_MODULES:
        try:
            path.relative_to(_SRC_ROOT / "core" / "parsing")
            return True
        except ValueError:
            pass
    # core/ modules may use date.fromisoformat directly because they share the
    # same package layer as the canonical parsers and cannot import from
    # core.parsing._dates without risking circular-import chains through
    # get_logger → config → parsing._dates.
    try:
        path.relative_to(_SRC_ROOT / "core")
        return True
    except ValueError:
        pass
    return False


# ---------------------------------------------------------------------------
# AST-based detection of date.fromisoformat( calls
# ---------------------------------------------------------------------------


_DATE_FROMISOFORMAT_ORIGIN = "datetime.date.fromisoformat"
"""The single origin every in-scope spelling must resolve to."""

_UNREBOUND_DATETIME_DEFAULTS: Mapping[str, str] = {
    "date": "datetime.date",
    "datetime": "datetime",
}
"""Seed origins for the stdlib names a module has not rebound.

A module reading ``date.fromisoformat`` without a resolvable ``from datetime
import date`` in this tree (a first-party re-export, a ``TYPE_CHECKING``-only
import) still means the date class, so the bare spelling stays in scope and
alias awareness cannot narrow what the gate governs. A module that *does*
rebind the name — ``from datetime import datetime`` making ``datetime`` the
class, not the module — keeps its own binding and is judged on that.
"""


def _datetime_binding_map(tree: ast.AST) -> dict[str, str]:
    """Return the module's import bindings seeded with the unrebound stdlib defaults."""
    bindings = import_binding_map(tree)
    for name, origin in _UNREBOUND_DATETIME_DEFAULTS.items():
        bindings.setdefault(name, origin)
    return bindings


def _fromisoformat_call_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``date.fromisoformat(...)`` calls under any local spelling.

    Import-alias aware by resolution rather than by spelling: every call's
    dotted callee is resolved through the module's own import bindings and
    compared against the one canonical origin, so ``date.fromisoformat``,
    ``_date.fromisoformat`` (``from datetime import date as _date``),
    ``dt.date.fromisoformat`` (``import datetime as dt``),
    ``datetime.date.fromisoformat``, and a handle rebound through a local
    variable all collapse onto the same match.

    The naive shape this replaces required the callee to be spelled literally
    ``date.fromisoformat``, so any import alias walked straight past it and the
    gate reported green over a live call site.
    """
    bindings = _datetime_binding_map(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if resolve_dotted_origin(qualified_name(node.func), bindings) == _DATE_FROMISOFORMAT_ORIGIN:
            yield node.lineno


# ---------------------------------------------------------------------------
# Violation collectors
# ---------------------------------------------------------------------------


def _is_lower_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "lower"
        and not node.args
        and not node.keywords
    )


def _is_bool_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value in {"true", "false"}


def _inline_bool_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``value.lower() == "true"/"false"`` comparisons."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        if (_is_lower_call(node.left) and _is_bool_literal(node.comparators[0])) or (
            _is_bool_literal(node.left) and _is_lower_call(node.comparators[0])
        ):
            yield node.lineno


def _collect_fromisoformat_violations(
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> list[str]:
    """Return ``file:line`` strings for bare ``date.fromisoformat()`` calls.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file. When omitted, fall back to walk-and-parse so
    the helper's no-arg signature stays compatible with importlib
    callers.
    """
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for lineno in _fromisoformat_call_linenos(tree):
            violations.append(f"{repo_relative(path)}:{lineno}")
    return violations


def _collect_inline_bool_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for lineno in _inline_bool_linenos(tree):
            violations.append(f"{repo_relative(path)}:{lineno}")
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_bare_date_fromisoformat(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Zero ``date.fromisoformat(`` calls survive in production modules.

    All date parsing must go through ``_parse_iso8601_date`` or
    ``_parse_ddmmyyyy_date`` from ``cadrumo.core.parsing._dates``.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_fromisoformat_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare date.fromisoformat() call(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_iso8601_date() or _parse_ddmmyyyy_date() from cadrumo.core.parsing._dates.",
        )


@pytest.mark.parametrize(
    ("source", "expected_hits"),
    (
        pytest.param(
            "from datetime import date\n\nd = date.fromisoformat(raw)\n",
            1,
            id="bare-date-import",
        ),
        pytest.param(
            "from datetime import date as _date\n\nd = _date.fromisoformat(raw)\n",
            1,
            id="renamed-date-import",
        ),
        pytest.param(
            "import datetime as dt\n\nd = dt.date.fromisoformat(raw)\n",
            1,
            id="renamed-datetime-module",
        ),
        pytest.param(
            "import datetime\n\nd = datetime.date.fromisoformat(raw)\n",
            1,
            id="qualified-datetime-module",
        ),
        pytest.param(
            "import datetime.timezone\n\nd = datetime.date.fromisoformat(raw)\n",
            1,
            id="submodule-import-binds-root",
        ),
        pytest.param(
            "from datetime import date as _date\n\n_iso = _date.fromisoformat\n\nd = _iso(raw)\n",
            # The assignment itself is not a call; only the rebound invocation is.
            1,
            id="handle-rebound-through-a-variable",
        ),
        pytest.param(
            "def parse(raw):\n    from datetime import date as _d\n\n    return _d.fromisoformat(raw)\n",
            1,
            id="function-local-aliased-import",
        ),
        pytest.param(
            "from datetime import date as _date\n\na = _date\nb = a\n\nd = b.fromisoformat(raw)\n",
            1,
            id="rebinding-chain",
        ),
    ),
)
def test_fromisoformat_detector_catches_every_alias_spelling(source: str, expected_hits: int) -> None:
    """Anti-tautology proof: a planted violation is caught under every import alias.

    A structural gate with no demonstration that it *can* fail is
    indistinguishable from one that always passes. Each case plants the
    forbidden call in a spelling the earlier literal-``date`` check walked
    past, and asserts the live detector fires. Sources are parsed in memory:
    no violation is committed to the tree.
    """
    hits = list(_fromisoformat_call_linenos(ast.parse(source)))

    assert len(hits) == expected_hits, f"detector missed the planted violation in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param(
            "from datetime import datetime\n\nd = datetime.fromisoformat(raw)\n",
            id="datetime-class-is-out-of-scope",
        ),
        pytest.param(
            "from ..core.parsing import parse_iso8601_date\n\nd = parse_iso8601_date(raw)\n",
            id="canonical-helper-call",
        ),
        pytest.param(
            "from datetime import datetime as date\n\nd = date.fromisoformat(raw)\n",
            id="date-name-rebound-to-the-datetime-class",
        ),
        pytest.param(
            "class Custom:\n    @staticmethod\n    def fromisoformat(raw):\n        return raw\n\n"
            "d = Custom.fromisoformat(raw)\n",
            id="unrelated-fromisoformat-owner",
        ),
    ),
)
def test_fromisoformat_detector_ignores_out_of_scope_shapes(source: str) -> None:
    """The gate governs the date class only; alias awareness must not widen its reach.

    ``datetime.fromisoformat`` is a different parser with a different canonical
    owner, and a local name rebound to the ``datetime`` class is judged on that
    binding rather than on the letters ``date``.
    """
    assert list(_fromisoformat_call_linenos(ast.parse(source))) == []


def test_no_inline_bool_lower_comparison(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Zero ``value.lower() == \"true\"/\"false\"`` patterns survive in production modules.

    All boolean string parsing must go through ``_parse_bool`` from
    ``cadrumo.core.parsing._utils``.
    """
    violations = _collect_inline_bool_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline bool-parsing pattern(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_bool() from cadrumo.core.parsing._utils.",
        )
