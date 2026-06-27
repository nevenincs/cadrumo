"""Inventory test: every production cast() call must carry a CAST-RATIONALE-* marker.

Rule
----
For every ``cast(`` occurrence in a non-test production module under
``src/aeat/``, either:

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
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import cast_rationale_violations

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


def test_every_cast_has_rationale_marker(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Every production cast() call must have a CAST-RATIONALE-* comment.

    Consumes the session-scoped AST cache so the per-file parse cost is
    amortised across the full ratchet suite.
    """
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}\n\n"
            "Add a '# CAST-RATIONALE-<SLUG>: ...' comment on the cast line or "
            "in the immediately preceding comment block.",
        )
