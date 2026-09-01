"""Production modules must obtain wall-clock time via :func:`~core.time.now`.

No production module under ``src/cadrumo/`` may read the wall clock off the
``datetime`` class inline. All call-sites delegate to the public
:mod:`~core.time` clock facade so the production clock is uniform, traceable,
and compatible with :func:`~core.time.frozen_clock` replay.

The detected surface is every wall-clock read on ``datetime``:

- ``datetime.now(UTC)`` and ``datetime.now(tz=UTC)`` — the canonical spelling.
- ``datetime.now(timezone.utc)`` — the same object under its other spelling.
  ``UTC`` *is* ``timezone.utc``, so recognising only one spelling would let a
  byte-for-byte equivalent call through; the matcher compares the constant, not
  the source text.
- ``datetime.utcnow()`` and a bare ``datetime.now()`` — both read the same clock
  and return a *naive* value, so they are strictly worse than the aware form
  already banned. A detector that caught only the aware spelling would have been
  hardest on the safest shape.
- ``datetime.now(<any other tzinfo>)`` — an arbitrary-zone read defeats
  :func:`~core.time.frozen_clock` replay exactly as a UTC read does, so the rule
  is about the clock read, not about the zone it is rendered in.

Every one of the shapes above is reported through one matcher rather than an
allowlist, because each is the same act (reading the clock off ``datetime``)
written differently — not a separate rule with its own exceptions.

The permanent exclusions are test infrastructure and the canonical
implementation module itself. Conditional defaults of the shape
``if now is not None else datetime.now(...)`` remain permitted only on
constructor/helper signatures that already accept an injectable clock argument
named ``now``: those sites already carry the replay seam in their signature.

Known blind spot, deliberately not closed: a call reached through a rebound
alias (``import datetime as dt`` then ``dt.now(UTC)``) is invisible, because the
matcher resolves the callee by its literal leaf name rather than through the
module's import bindings. The tree carries no such alias today — the two aliased
``datetime`` imports in production are used for ``timedelta`` and for a type
annotation, never for a clock read. Closing it needs the import-binding
resolution the parsing-enrollment gate performs; until a real site justifies
that cost, this paragraph is the honest statement of reach.

See Also:
    :mod:`~core.time`
        Canonical wall-clock facade and deterministic replay seam.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by this ratchet.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_CADRUMO
_CLOCK_MODULE = _SRC_ROOT / "core" / "time" / "clock.py"
_TEST_INFRA_MODULES: frozenset[Path] = frozenset(
    {
        _SRC_ROOT / "adapters" / "persistence" / "storage" / "envelope" / "tests" / "_repository_contract_support.py",
        _SRC_ROOT / "tests" / "secure_sql.py",
    },
)


def _is_excluded(path: Path) -> bool:
    if path in _TEST_INFRA_MODULES:
        return True
    try:
        path.relative_to(_CLOCK_MODULE.parent)
        return path.name == _CLOCK_MODULE.name
    except ValueError:
        return False


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_utc_name(node: ast.AST) -> bool:
    """Return True for either spelling of the one UTC constant.

    ``datetime.UTC`` and ``datetime.timezone.utc`` are the same object; matching
    only the upper-case spelling would pass an identical call written the other
    way.
    """
    return leaf_name(node) in {"UTC", "utc"}


def _describe_clock_read(node: ast.AST) -> str | None:
    """Describe an inline wall-clock read off ``datetime``, or ``None``.

    Every returned description names one act — reading the clock off the
    ``datetime`` class — under the spelling the author actually used, so the
    failure message points at the real line rather than a generic category.
    """
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Attribute):
        return None
    if leaf_name(node.func.value) != "datetime":
        return None
    if node.func.attr == "utcnow":
        return "datetime.utcnow() [naive, deprecated]"
    if node.func.attr != "now":
        return None
    if not node.args and not node.keywords:
        return "datetime.now() [naive local time]"
    if node.args and _is_utc_name(node.args[0]):
        return "datetime.now(UTC)"
    if any(keyword.arg == "tz" and _is_utc_name(keyword.value) for keyword in node.keywords):
        return "datetime.now(tz=UTC)"
    return "datetime.now(<tz>) [non-UTC zone]"


def _is_datetime_now_utc_call(node: ast.AST) -> bool:
    """Return True for any inline wall-clock read off the ``datetime`` class."""
    return _describe_clock_read(node) is not None


def _is_now_is_not_none_test(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "now"
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is None
    )


def _enclosing_function_accepts_now(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef):
            return any(arg.arg == "now" for arg in [*parent.args.args, *parent.args.kwonlyargs])
        current = parent
    return False


def _is_documented_now_fallback(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return (
        isinstance(parent, ast.IfExp)
        and parent.orelse is node
        and _is_now_is_not_none_test(parent.test)
        and _enclosing_function_accepts_now(parent, parents)
    )


def _collect_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline clock call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            description = _describe_clock_read(node)
            if description is None or _is_documented_now_fallback(node, parents):
                continue
            assert isinstance(node, ast.Call)
            violations.append(f"{repo_relative(path)}:{node.lineno}  {description}")
    return violations


def test_no_inline_datetime_now_utc(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Production modules MUST route wall-clock reads through :func:`~core.time.now`."""
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline datetime clock read(s) outside the canonical clock module:\n  {joined}\n\n"
            "Replace each call with now() from cadrumo.core.time. The only permitted\n"
            "inline pattern is the documented escape hatch:\n"
            "    timestamp = now if now is not None else datetime.now(UTC)\n"
            "on signatures that already accept an injectable ``now`` argument.",
        )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        pytest.param("x = datetime.now(UTC)\n", "datetime.now(UTC)", id="aware-positional"),
        pytest.param("x = datetime.now(tz=UTC)\n", "datetime.now(tz=UTC)", id="aware-keyword"),
        pytest.param("x = datetime.now(timezone.utc)\n", "datetime.now(UTC)", id="aware-timezone-utc-spelling"),
        pytest.param("x = datetime.now(tz=timezone.utc)\n", "datetime.now(tz=UTC)", id="aware-keyword-timezone-utc"),
        pytest.param("x = datetime.datetime.now(UTC)\n", "datetime.now(UTC)", id="module-qualified"),
        pytest.param("x = datetime.now()\n", "datetime.now() [naive local time]", id="naive-bare"),
        pytest.param("x = datetime.utcnow()\n", "datetime.utcnow() [naive, deprecated]", id="utcnow"),
        pytest.param("x = datetime.now(MADRID_TZ)\n", "datetime.now(<tz>) [non-UTC zone]", id="non-utc-zone"),
    ),
)
def test_detector_catches_every_clock_read_spelling(source: str, expected: str) -> None:
    """Anti-tautology proof: each clock-read spelling is planted and must be seen.

    Before this proof existed the matcher recognised only the two ``UTC``
    spellings, so ``timezone.utc``, ``utcnow()``, a bare naive ``now()``, and any
    non-UTC zone all passed a green gate. None of those shapes was present in the
    tree, so the blindness cost nothing — but nothing except this proof would have
    revealed it before it did. Sources are parsed in memory; no violation is
    committed to the tree.
    """
    reads = [_describe_clock_read(node) for node in ast.walk(ast.parse(source))]
    found = [read for read in reads if read is not None]

    assert found == [expected], f"detector missed the planted clock read in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("x = now()\n", id="canonical-facade-call"),
        pytest.param("x = clock.now()\n", id="unrelated-object-now"),
        pytest.param("x = time.time()\n", id="monotonic-duration-probe"),
        pytest.param("x = date.today()\n", id="date-today-out-of-scope"),
        pytest.param("x = datetime(2026, 1, 1, tzinfo=UTC)\n", id="explicit-construction"),
        pytest.param("x = datetime.fromisoformat(raw)\n", id="parsing-not-a-clock-read"),
    ),
)
def test_detector_stays_silent_on_non_clock_reads(source: str) -> None:
    """The other direction: the matcher must not claim ground it does not hold.

    ``time.time()`` and ``date.today()`` are genuinely outside this gate: the
    first is used for duration probes where replay is irrelevant, the second is a
    date rather than an instant. Pinning them keeps a later widening honest about
    which surface it is actually extending.
    """
    assert [read for read in (_describe_clock_read(n) for n in ast.walk(ast.parse(source))) if read is not None] == []
