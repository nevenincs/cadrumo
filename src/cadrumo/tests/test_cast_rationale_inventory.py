"""Inventory test: every production cast() call must carry a CAST-RATIONALE-* marker.

Rule
----
For every ``cast(`` occurrence in a non-test production module under
``src/cadrumo/``, either:

- the same line contains ``CAST-RATIONALE-``, OR
- scanning upward through immediately adjacent comment / blank lines reaches
  a line containing ``CAST-RATIONALE-`` before hitting any code line.

Rationale
---------
Unguarded ``cast()`` calls erase type-system information without leaving an
explanation for future readers.  The marker scheme enforces a concise,
grep-able audit trail at every escape hatch.

Exclusions
----------
- ``test_*.py`` files: test suites may reference cast() in assertions without
  a production rationale marker.
- Lines where ``cast(`` appears only inside a Python *string literal*
  (docstrings, rst-style prose) are excluded because they are not actual
  cast calls.  The heuristic: strip the line; if the only ``cast(`` is
  preceded by a quote character or occurs inside a triple-quoted block, skip.
  Rather than attempting full parse, we use a conservative AST walk per file
  to locate real ``cast()`` call nodes and their line numbers.

Known blind spot: the import alias
----------------------------------
The call matcher recognises ``cast(...)`` by the bare name and ``typing.cast``
/ ``t.cast`` by module attribute. It resolves nothing through the module's
import bindings, so a rebound alias hides the call completely::

    from typing import cast as _cast     # matcher sees no ``cast`` name
    import typing as ty                  # matcher accepts only ``typing``/``t``

This is not hypothetical rot. The sibling parsing-enrollment gate shipped the
same shape and was genuinely bitten by it: its spelling-matched check demanded a
literal ``date.fromisoformat`` callee and reported green over a real
``_date.fromisoformat`` call reached through ``from datetime import date as
_date``. That gate now resolves callees through the import bindings; this one
does not.

The gap is left open deliberately, because the tree carries zero aliased
``cast`` imports and zero ``typing`` module aliases — every importing module
uses the plain ``from typing import cast`` form. Rather than pin the blindness
itself, :func:`test_no_aliased_cast_import_shadows_the_matcher` guards the
precondition that makes it safe: it fires the day an alias is introduced, which
is the moment the blindness starts costing something, instead of the day someone
repairs the matcher.

See Also:
    :func:`~tests._inventory.cast_rationale_violations`
        Shared AST inventory helper that locates production ``cast()`` calls
        missing adjacent rationale markers.
    :mod:`~tests.test_type_ignore_rationale_inventory`
        Companion escape-hatch ratchet that also accepts historical
        ``CAST-RATIONALE-*`` markers for type-ignore suppressions.
    :mod:`~tests.test_any_param_rationale_inventory`
        Parameter-level ``Any`` rationale ratchet that protects the same typed
        boundary documentation standard.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from .inventory import (
    CAST_RATIONALE_MARKER,
    cast_call_linenos,
    cast_rationale_violations,
    has_marker_on_line_or_adjacent_comment_block,
    production_ast_items,
    repo_relative,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _collect_violations(source_tree_ast: Mapping[Path, ast.AST] | None = None) -> list[str]:
    """Return the list of ``cast()`` sites that lack a rationale marker.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file and read the raw source text only to render line
    snippets. When omitted (external callers via ``retired_campaign_aggregate``
    importlib path), fall back to the original walk-and-parse so the
    helper's public signature stays no-arg compatible.
    """
    return cast_rationale_violations(source_tree_ast)


def test_every_cast_has_rationale_marker(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every production cast() call must have a CAST-RATIONALE-* comment.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block.",
        )


def _unmarked(source: str) -> list[int]:
    """Return line numbers of ``cast()`` calls in *source* lacking a marker."""
    lines = source.splitlines()
    return [
        lineno
        for lineno in cast_call_linenos(ast.parse(source))
        if not has_marker_on_line_or_adjacent_comment_block(lines, lineno, CAST_RATIONALE_MARKER)
    ]


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("x = cast(int, y)\n", id="bare-cast"),
        pytest.param("x = typing.cast(int, y)\n", id="typing-qualified"),
        pytest.param("x = t.cast(int, y)\n", id="t-qualified"),
        pytest.param("def f():\n    return cast(int, y)\n", id="nested-in-function"),
        pytest.param("x = cast(\n    int,\n    y,\n)\n", id="multiline-call"),
        pytest.param("# an unrelated comment\nx = cast(int, y)\n", id="comment-without-marker"),
    ),
)
def test_detector_fires_on_an_unmarked_cast(source: str) -> None:
    """Anti-tautology proof: an unmarked cast is planted and must be reported.

    Sources are parsed in memory; no violation is committed to the tree.
    """
    assert _unmarked(source), f"detector missed the planted unmarked cast in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("x = cast(int, y)  # CAST-RATIONALE-BOUNDARY: untyped API\n", id="marker-same-line"),
        pytest.param("# CAST-RATIONALE-BOUNDARY: untyped API\nx = cast(int, y)\n", id="marker-comment-above"),
        pytest.param(
            "# CAST-RATIONALE-BOUNDARY:\n# reason continues here\nx = cast(int, y)\n",
            id="marker-multiline-comment-block",
        ),
        pytest.param('DOC = "we call cast(int, y) at this boundary"\n', id="cast-inside-string-literal"),
        pytest.param("x = downcast(int, y)\n", id="name-merely-ending-in-cast"),
    ),
)
def test_detector_stays_silent_on_marked_or_unreal_casts(source: str) -> None:
    """The other direction: a documented cast, or a non-call, is not a violation.

    ``downcast`` matters structurally — the matcher compares the identifier, so a
    substring check would have flagged it. The string-literal case is the
    documented exclusion, and is why the matcher walks the AST rather than lines.
    """
    assert _unmarked(source) == []


def test_no_aliased_cast_import_shadows_the_matcher() -> None:
    """No production module may rebind ``cast`` or ``typing`` to an alias.

    The matcher resolves callees by literal name, so ``from typing import cast as
    _cast`` or ``import typing as ty`` makes every cast in that module invisible
    and silently disables this gate there. The sibling parsing gate shipped the
    identical shape and was genuinely bitten by it before it grew import-binding
    resolution.

    Guarding the precondition rather than pinning the blindness means this fires
    when an alias is introduced — the moment the gap starts costing something —
    instead of when someone repairs the matcher.
    """
    offenders: list[str] = []
    for path, tree in production_ast_items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                offenders.extend(
                    f"{repo_relative(path)}:{node.lineno}  cast imported as '{alias.asname}'"
                    for alias in node.names
                    if alias.name == "cast" and alias.asname
                )
            elif isinstance(node, ast.Import):
                offenders.extend(
                    f"{repo_relative(path)}:{node.lineno}  typing imported as '{alias.asname}'"
                    for alias in node.names
                    if alias.name == "typing" and alias.asname not in (None, "t")
                )

    assert not offenders, (
        "cast()/typing alias(es) the rationale matcher cannot see:\n  "
        + "\n  ".join(offenders)
        + "\n\nEither use the plain 'from typing import cast' / 'import typing' form, "
        "or port the import-binding resolution from the parsing-enrollment gate so "
        "aliased callees resolve."
    )
