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
- ``src/cadrumo/core/parsing/dates.py``: the canonical implementation itself.
- ``src/cadrumo/core/parsing/utils.py``: the canonical bool-parsing implementation.

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

from .inventory import (
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
        "utils.py",
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


_BOOLEAN_TOKENS: frozenset[str] = frozenset(
    {"true", "false", "1", "0", "yes", "no", "y", "n", "si", "sí", "s", "verdadero", "falso"},
)
"""Words that mean true or false to somebody, in either language.

Membership in this set is what makes a literal collection a *boolean
vocabulary* rather than an ordinary set of strings. It is deliberately wider
than the canonical parser's own sets: the gate must recognise a hand-rolled
vocabulary in order to refuse it, including spellings the canonical parser
does not accept.
"""


def _literal_string_members(node: ast.AST) -> frozenset[str]:
    """Return the string constants of a literal set/tuple/list, or empty."""
    if not isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return frozenset[str]()
    return frozenset(e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))


def _membership_bool_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``token in {"true", "1", "yes"}`` style comparisons.

    The shape the equality check below cannot see, and the shape every real
    hand-rolled coercion in this codebase actually used. Two or more members,
    all of them boolean words, is the signature: it does not fire on an
    ordinary string set, and one lone token is left alone because a single
    ``in {"x"}`` is an equality test in disguise rather than a vocabulary.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], (ast.In, ast.NotIn)):
            continue
        members = _literal_string_members(node.comparators[0])
        if len(members) >= 2 and {m.lower() for m in members} <= _BOOLEAN_TOKENS:
            yield node.lineno


def _comparison_bool_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``x == "true"`` / ``x != "false"`` under any receiver.

    Deliberately does NOT require a ``.lower()`` receiver, which is what the
    original check demanded. That requirement is why the live wizard sites --
    ``row.get("convivencia", "") != "false"`` and ``row.get("custodia-
    compartida", "") == "true"`` -- fell through: no ``.lower()``, and one of
    them an inequality. Comparing anything against the literal ``"true"`` or
    ``"false"`` is boolean parsing whatever the receiver looks like, so the
    receiver is not part of the signature.

    ``!=`` matters as much as ``==``. A negative comparison is a negative
    list: ``!= "false"`` reads everything except one spelling as true, so an
    operator's ``no`` becomes yes -- the exact defect on the descendant facts
    that gate mínimo por descendientes.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        if not isinstance(node.ops[0], (ast.Eq, ast.NotEq)) or len(node.comparators) != 1:
            continue
        if _is_bool_literal(node.left) or _is_bool_literal(node.comparators[0]):
            yield node.lineno


def _inline_bool_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of inline boolean parsing, under all three shapes.

    WHAT THIS SEES: a comparison against the literal ``"true"``/``"false"``
    (``==`` or ``!=``, with or without ``.lower()``), and membership in a
    literal set/tuple/list whose members are all boolean words.

    WHAT IT DOES NOT SEE, stated because a contract wider than its detector is
    the defect this gate itself shipped: a vocabulary held in a module-level
    constant rather than written inline at the comparison; a dict lookup used
    as a coercion (``{"true": True}.get(raw)``); a chained comparison; a
    regex; and anything assembled at runtime. A green result here means "none
    of the three shapes above appear", not "every boolean parse is canonical".

    The history is the argument for saying so. This gate claimed all boolean
    parsing funnelled through the canonical parser while detecting exactly one
    shape -- equality with a ``.lower()`` receiver. Every divergent coercion
    the codebase grew was one of the other two, so the gate ran green over all
    of them, including the two whose disagreement turned a taxpayer's ``si``
    into ``False`` on exemption-gating fields.
    """
    yield from _comparison_bool_linenos(tree)
    yield from _membership_bool_linenos(tree)


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


_EXEMPT_BOOL_SITES: Mapping[str, tuple[int, str]] = {
    "src/cadrumo/domain/user_profile/values.py": (
        1,
        "Not operator input. This is the fact carrier decoding its own JSON round-trip, and it "
        "accepts only the two canonical tokens it emitted. Widening it to the operator vocabulary "
        "would promote a stored 'si' into a typed bool at re-parse, which is a different contract: "
        "the carrier's job is to restore what it wrote, not to interpret what a person typed.",
    ),
    "src/cadrumo/domain/contribuyente/descendant_facts.py": (
        2,
        "Reads back the canonical 'true'/'false' this same module writes (see "
        "descendant_facts_from_list). A stored value it produced needs no vocabulary; the operator "
        "input on the flag-parsing path above it does, and that path was converted.",
    ),
    "src/cadrumo/application/wizard/persistence.py": (
        1,
        "parse_canonical reads a token this application itself wrote, and its strictness is a "
        "GUARD rather than an oversight: accepting 'True' or 'TRUE' would silently admit an "
        "unlowercased str(bool) that escaped _render_fact_value, corrupting the round-trip "
        "instead of failing it. Its own test pins that, rejecting 'True', 'TRUE' and even 'yes'. "
        "The operator vocabulary belongs at validate_confirm, which is where a person types; "
        "widening it here would disable the guard. The descendiente reads in the same file are "
        "NOT exempt -- they were converted, which is why this is granted for one site only.",
    ),
    "src/cadrumo/domain/calculations/registry/export_value_policy.py": (
        2,
        "A FALSE POSITIVE in the strictest direction. These sites do not PARSE a boolean, they "
        "VALIDATE one character of a fixed-width AEAT export record: a selected/unselected field "
        "is literally ASCII 0 or 1 and nothing else. parse_bool accepts a wider vocabulary, so "
        "substituting it here would admit 'true' and 'si' into a byte-exact official record. The "
        "canonical parser is a superset of what these sites accept, which is exactly why it is "
        "the wrong tool: for a validator, a wider vocabulary is a weaker guard.",
    ),
    "src/cadrumo/domain/calculations/registry/record_design.py": (
        1,
        "A FALSE POSITIVE, and the reason is worth stating so nobody 'fixes' it. The tokens are "
        "'no' and 'n' -- the Spanish abbreviation for numero -- and the code is looking for a "
        "spreadsheet column headed N. or No. Nothing here is a boolean. The detector matches on "
        "the words rather than the meaning, and these two words are the collision.",
    ),
}
"""Sites the detector flags that are not hand-rolled boolean vocabularies.

Each entry is ``(expected hits, reason)``. Keyed by file rather than by line so
an edit that moves the code does not strand the exemption -- but the COUNT is
what stops a file-keyed exemption from covering more than it was granted for.
Without it, exempting a file for two canonical round-trips would silently
excuse a third coercion someone adds later, which is the same
wider-than-intended shape this whole gate exists to close. The count only moves
when the number of flagged sites in that file moves, and that is exactly the
event worth failing on.
"""


def _collect_inline_bool_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        relative = str(repo_relative(path)).replace("\\", "/")
        hits = list(_inline_bool_linenos(tree))
        if relative in _EXEMPT_BOOL_SITES:
            expected, _ = _EXEMPT_BOOL_SITES[relative]
            if len(hits) == expected:
                continue
            violations.extend(
                f"{repo_relative(path)}:{lineno} "
                f"(exempt file now has {len(hits)} flagged site(s), granted for {expected})"
                for lineno in hits
            )
            continue
        violations.extend(f"{repo_relative(path)}:{lineno}" for lineno in hits)
    return violations


def _flagged_files() -> set[str]:
    """Every non-excluded file the detector currently flags, exemptions included."""
    return {
        str(repo_relative(path)).replace("\\", "/")
        for path, tree in production_ast_items(None)
        if not _is_excluded(path) and any(True for _ in _inline_bool_linenos(tree))
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_bare_date_fromisoformat(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Zero ``date.fromisoformat(`` calls survive in production modules.

    All date parsing must go through ``_parse_iso8601_date`` or
    ``_parse_ddmmyyyy_date`` from ``cadrumo.core.parsing.dates``.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_fromisoformat_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare date.fromisoformat() call(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_iso8601_date() or _parse_ddmmyyyy_date() from cadrumo.core.parsing.dates.",
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
    ``cadrumo.core.parsing.utils``.
    """
    violations = _collect_inline_bool_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline bool-parsing pattern(s) found in production code:\n  {joined}\n\n"
            "Replace with parse_bool() from cadrumo.core.parsing. A hand-rolled vocabulary drifts "
            "from every other one: the maritime reader's took no Spanish at all while the filing "
            "layer's did, so 'si' meant yes at one boundary and no at the next.",
        )


def test_every_bool_exemption_names_a_live_site() -> None:
    """A stale exemption is a hole; it must not outlive the site it excuses.

    An exemption whose file no longer trips the detector silently widens the
    gate: the next hand-rolled vocabulary added to that file inherits a pass
    nobody granted it.
    """
    stale = sorted(site for site in _EXEMPT_BOOL_SITES if site not in _flagged_files())

    assert not stale, f"bool exemptions naming sites the detector no longer flags: {stale}"


def test_every_bool_exemption_states_a_reason() -> None:
    """An exemption without a reason is an unexplained hole in the gate."""
    unreasoned = sorted(site for site, (_, reason) in _EXEMPT_BOOL_SITES.items() if not reason.strip())

    assert not unreasoned, f"bool exemptions without a stated reason: {unreasoned}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param('x = token in {"true", "1", "yes"}\n', id="the-maritime-reader-shape"),
        pytest.param('x = normalized in {"1", "true", "s", "si", "yes"}\n', id="the-filing-layer-shape"),
        pytest.param('x = raw.lower() in ("true", "1", "si", "sí", "yes")\n', id="tuple-not-set"),
        pytest.param('x = token not in {"false", "0", "no"}\n', id="negated-membership"),
        pytest.param('x = value.lower() == "true"\n', id="the-equality-shape-already-covered"),
    ),
)
def test_the_detector_catches_every_hand_rolled_vocabulary_shape(source: str) -> None:
    """Anti-tautology proof, and the regression guard for this gate's own blind spot.

    Every one of these is a shape that shipped in production while the gate
    reported green, because the detector only ever matched the last case.
    Sources are parsed in memory; no violation is committed to the tree.
    """
    assert list(_inline_bool_linenos(ast.parse(source))), f"detector missed the planted vocabulary in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param('x = name in {"alice", "bob"}\n', id="an-ordinary-string-set"),
        pytest.param('x = code in {"ES", "FR", "PT"}\n', id="country-codes"),
        pytest.param('x = flag in {"true"}\n', id="a-single-token-is-an-equality-test"),
        pytest.param('x = value in {"true", "maybe", "false"}\n', id="not-entirely-boolean-words"),
    ),
)
def test_the_detector_leaves_non_boolean_vocabularies_alone(source: str) -> None:
    """Widening the detector must not make it fire on ordinary string membership.

    A gate that flags every ``in {...}`` would be worse than the blind one it
    replaces: it would train the next author to reach for the exemption map
    rather than the canonical parser.
    """
    assert list(_inline_bool_linenos(ast.parse(source))) == [], f"detector over-reached on:\n{source}"
