"""Inventory ratchet: parameter-level ``Any`` annotations must carry an inline rationale marker.

Rule
----
Every production function whose parameter annotations include a bare ``Any``
(or a generic that contains bare ``Any`` at a parameter position) must have one
of the following marker tokens in the preceding 3 source lines:

- ``KWARGS-ANY-RATIONALE-``  — for circular-import or structural reasons
- ``ANY-RETURN-RATIONALE-``  — for return-type escapes (also covers param
  sites when the same rationale applies to the full signature)
- ``ADAPTER-INTERNAL-ALIAS-RATIONALE-``  — for third-party untyped resources

Structural prevention (ratchet history)
--------------------------------
This test AST-walks **all** production Python files under ``src/cadrumo/``
(excluding test files) so every new file is automatically covered.

The backlog ``_KNOWN_VIOLATING_LINES`` is now empty and the gate enforces a hard
zero: every site it once carried has been remediated. See the comment on that
constant for why its 25 former entries were deleted rather than refreshed.

Reach of the ``Any`` matcher
----------------------------
An annotation counts as carrying ``Any`` under every spelling — the bare name,
``typing.Any``, any nesting inside a subscript, union, tuple, or ``Callable``
parameter list, and a quoted string annotation, which is re-parsed. These are
one annotation written differently, so they resolve through one recursion
rather than accreting an exemption per spelling.

The matcher is annotation-level and therefore says nothing about a parameter
left *unannotated* — an implicit ``Any`` under a permissive type checker is
outside this gate's reach by construction, and the type checker rather than
this ratchet is what refuses it.

Exclusions
----------
- Files whose name starts with ``test_`` or ends with ``_test.py``.
- Lambda nodes (no function-level marker convention applies; the body is
  usually on one line and the annotation is almost never ``Any``).

See Also:
    :func:`~tests._inventory.production_ast_items`
        Shared AST inventory used to scan production functions for parameter
        ``Any`` annotations.
    :mod:`~tests.test_type_ignore_rationale_inventory`
        Companion suppression ratchet that mirrors this marker-enrollment
        pattern for ``# type: ignore`` sites.
    :mod:`~tests.test_cast_rationale_inventory`
        Typed-boundary escape-hatch guard for runtime ``cast()`` calls.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# Marker token prefixes — any of these in a preceding line satisfies the rule.
_MARKER_TOKENS: tuple[str, ...] = (
    "KWARGS-ANY-RATIONALE-",
    "ANY-RETURN-RATIONALE-",
    "ADAPTER-INTERNAL-ALIAS-RATIONALE-",
)

# How many lines before the function ``def`` line are inspected for markers.
_CONTEXT_LINES = 3

# ---------------------------------------------------------------------------
# Backlog of known-violating sites. EMPTY, and that is the terminal state the
# ratchet was built to reach: every site it once held has been remediated with a
# marker or a concrete type, so the gate now enforces a hard zero.
#
# It previously held 25 entries, every one of which had gone inert. The key is
# (relative-path, function-def-lineno), and a line number is not a stable
# identity for a function: ordinary edits above a def shift it, so each entry
# stopped naming the site it was written for. Measured against the live
# collector, all 25 exempted nothing.
#
# Inert is not harmless. A stale entry does not decay into a no-op, it decays
# into a landmine: it silently pre-authorises whatever function comes to start
# at that coordinate later, for a reason nobody chose. Twenty-five arbitrary
# (file, line) pairs were standing as permanent exemptions for functions not yet
# written. That is why they are deleted rather than refreshed.
#
# Do NOT re-add entries here. The remedy for a new parameter-level ``Any`` is a
# marker comment naming the reason, or the concrete type. If a backlog ever
# genuinely needs re-opening, key it on something that survives an edit — the
# qualified function name — never on a line number.
# ---------------------------------------------------------------------------
_KNOWN_VIOLATING_LINES: frozenset[tuple[str, int]] = frozenset[tuple[str, int]]()


def _has_any_annotation(annotation: ast.expr | None) -> bool:
    """Return True if *annotation* is or contains an ``Any``, under any spelling.

    The recursion covers every container an annotation can nest ``Any`` inside,
    because they are all one annotation written differently rather than separate
    rules needing separate exemptions:

    - ``Any`` and ``typing.Any`` — the bare name and its module-qualified form.
    - ``list[Any]``, ``dict[str, Any]``, ``tuple[Any, ...]`` — subscripts.
    - ``Callable[[Any], int]`` — the parameter list of a ``Callable`` is an
      :class:`ast.List`, not a tuple, so omitting it left the single most common
      way of hiding an ``Any`` inside a signature unreachable.
    - ``Any | None`` — union operands.
    - ``"Any"`` and ``"dict[str, Any]"`` — a string annotation is re-parsed, so
      quoting cannot launder the escape past the matcher.
    """
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name) and annotation.id == "Any":
        return True
    if isinstance(annotation, ast.Attribute) and annotation.attr == "Any":
        return True
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            return _has_any_annotation(ast.parse(annotation.value, mode="eval").body)
        except SyntaxError:
            return False
    if isinstance(annotation, ast.Subscript):
        return _has_any_annotation(annotation.value) or _has_any_annotation(annotation.slice)
    if isinstance(annotation, ast.Tuple | ast.List):
        return any(_has_any_annotation(e) for e in annotation.elts)
    if isinstance(annotation, ast.BinOp):
        return _has_any_annotation(annotation.left) or _has_any_annotation(annotation.right)
    return False


def _params_have_any(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Return True if any parameter of *node* carries an ``Any`` annotation."""
    all_args = list(node.args.args) + list(node.args.kwonlyargs)
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)
    return any(_has_any_annotation(a.annotation) for a in all_args)


def _preceding_lines_have_marker(source_lines: list[str], func_lineno: int) -> bool:
    """Return True if any of _CONTEXT_LINES before *func_lineno* contain a marker."""
    start = max(0, func_lineno - 1 - _CONTEXT_LINES)
    end = func_lineno - 1
    return any(any(m in line for m in _MARKER_TOKENS) for line in source_lines[start:end])


def _collect_violations(
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> list[tuple[str, int]]:
    """Walk all production files and return (rel_path, lineno) pairs without markers.

    Consumes the shared production AST cache so the per-file parse cost is
    paid once per session rather than per ratchet test. The cache holds
    every parseable ``.py`` file under ``src/cadrumo/``; this helper applies
    the test-surface exclusion (``test_*.py`` / ``*_test.py``) as the
    per-test filter.
    """
    violations: list[tuple[str, int]] = []
    for path, tree in production_ast_items(source_tree_ast):
        try:
            source_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _params_have_any(node):
                continue
            if _preceding_lines_have_marker(source_lines, node.lineno):
                continue
            rel = aeat_relative(path)
            violations.append((rel, node.lineno))
    return violations


def test_no_new_any_param_without_rationale(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """New parameter-level ``Any`` annotations must carry an inline rationale marker.

    This test uses a ratchet against ``_KNOWN_VIOLATING_LINES``:

    - Sites already in the ratchet are skipped (tracked for future cleanup).
    - Any site NOT in the ratchet must have a rationale marker in the 3 lines
      before the ``def`` keyword.
    - New files or new functions are automatically covered.

    To remediate a known-violating site: add a marker comment (preferred) or
    replace ``Any`` with the concrete type, then remove the entry from
    ``_KNOWN_VIOLATING_LINES``. The test will then lock that site at zero.

    Marker tokens (any one is sufficient):
      KWARGS-ANY-RATIONALE-<LABEL>
      ANY-RETURN-RATIONALE-<LABEL>
      ADAPTER-INTERNAL-ALIAS-RATIONALE-<LABEL>
    """
    all_violations = _collect_violations(source_tree_ast)
    new_violations = [(rel, lineno) for rel, lineno in all_violations if (rel, lineno) not in _KNOWN_VIOLATING_LINES]

    if new_violations:
        lines = "\n  ".join(f"{rel}:{lineno}" for rel, lineno in new_violations)
        raise AssertionError(
            f"{len(new_violations)} parameter-Any site(s) found without a rationale marker:\n"
            f"  {lines}\n\n"
            "Add one of the following marker tokens in the 3 lines before the function def:\n"
            "  # KWARGS-ANY-RATIONALE-<LABEL>: <reason>\n"
            "  # ANY-RETURN-RATIONALE-<LABEL>: <reason>\n"
            "  # ADAPTER-INTERNAL-ALIAS-RATIONALE-<LABEL>: <reason>\n"
            "Or replace Any with the concrete type if it is now known.\n"
            f"Backlog holds {len(_KNOWN_VIOLATING_LINES)} pre-existing sites; "
            "do NOT add new sites to the backlog — add a marker instead.",
        )


@pytest.mark.parametrize(
    "annotation",
    (
        pytest.param("Any", id="bare-name"),
        pytest.param("typing.Any", id="module-qualified"),
        pytest.param("list[Any]", id="subscript"),
        pytest.param("dict[str, Any]", id="subscript-two-args"),
        pytest.param("tuple[Any, ...]", id="tuple-ellipsis"),
        pytest.param("Any | None", id="union"),
        pytest.param("Callable[..., Any]", id="callable-return"),
        pytest.param("Callable[[Any], int]", id="callable-parameter-list"),
        pytest.param("Mapping[str, list[Any]]", id="nested-subscript"),
        pytest.param('"Any"', id="string-annotation"),
        pytest.param('"dict[str, Any]"', id="string-annotation-nested"),
    ),
)
def test_matcher_sees_every_any_spelling(annotation: str) -> None:
    """Anti-tautology proof: each spelling is planted and must be recognised.

    Two of these were unreachable before this proof existed. ``typing.Any`` was
    invisible because the matcher tested only for a bare name, and
    ``Callable[[Any], int]`` was invisible because a ``Callable`` parameter list
    is an :class:`ast.List` rather than a tuple — the single most common way an
    ``Any`` hides inside a signature. Annotations are parsed in memory; nothing
    is committed to the tree.
    """
    node = ast.parse(annotation, mode="eval").body

    assert _has_any_annotation(node), f"matcher missed the planted Any in: {annotation}"


@pytest.mark.parametrize(
    "annotation",
    (
        pytest.param("int", id="builtin"),
        pytest.param("dict[str, str]", id="fully-typed-mapping"),
        pytest.param("Callable[[int], str]", id="fully-typed-callable"),
        pytest.param("AnyStr", id="name-merely-starting-with-any"),
        pytest.param("Anything", id="name-merely-containing-any"),
        pytest.param('"dict[str, str]"', id="string-annotation-clean"),
        pytest.param('"not valid python ["', id="unparseable-string-annotation"),
    ),
)
def test_matcher_stays_silent_on_typed_annotations(annotation: str) -> None:
    """The other direction: a concrete annotation must not be reported.

    ``AnyStr`` and ``Anything`` matter structurally — the matcher compares the
    identifier, so a substring check would have flagged both. The unparseable
    string case pins that a quoted annotation the gate cannot read is treated as
    clean rather than raising out of the walk and taking the whole gate down.
    """
    node = ast.parse(annotation, mode="eval").body

    assert not _has_any_annotation(node)


def test_backlog_holds_no_inert_entries() -> None:
    """Every backlog entry must name a real, currently-violating site.

    A ``(path, lineno)`` key does not survive an edit above the function it
    names, so an entry that has drifted stops exempting its own site and starts
    silently pre-authorising whatever function later occupies that coordinate.
    This asserts the backlog earns its exemptions: today it is empty, and any
    future entry has to correspond to a site the collector actually reports.
    """
    current = set(_collect_violations())
    inert = sorted(entry for entry in _KNOWN_VIOLATING_LINES if entry not in current)

    assert not inert, (
        f"{len(inert)} backlog entry(ies) exempt nothing and now pre-authorise an "
        f"arbitrary line coordinate:\n  " + "\n  ".join(f"{rel}:{lineno}" for rel, lineno in inert) + "\n\n"
        "Delete them. Do not refresh the line numbers — key any genuine backlog on "
        "the qualified function name, which survives an edit."
    )
