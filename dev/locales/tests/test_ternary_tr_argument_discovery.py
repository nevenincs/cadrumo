"""Structural gate: a ternary ``tr()`` argument discovers BOTH branch keys.

``tr("key.a" if cond else "key.b")`` is a real production shape (four sites in
``entrypoints/cli`` and one in ``application/wizard`` at the time this gate was
written): the regex scanner in :class:`locales.manager.LocaleManager` only ever
captures the first quoted literal after ``tr(``, and the AST scanner's
call-site resolver required a plain :class:`ast.Constant` argument, so the
`else` branch's key was invisible to every downstream parity/coverage audit —
it could be deleted from every locale catalogue and nothing would notice.

This is a non-vacuous fixture proof, not an inline unit test of the private
helper: it writes a real ``.py`` module to ``tmp_path`` and drives it through
the same public :func:`scan_source_tree` entry point the parity gate calls, so
a regression that re-narrows the resolver back to "first branch only" reds
here rather than silently reopening the blind spot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .._ast_scanner import scan_source_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIXTURE_MODULE = """
from cadrumo.core.i18n import tr


def render_state(condition: bool) -> str:
    return tr(
        "fixture.ternary.branch_true"
        if condition
        else "fixture.ternary.branch_false"
    )
"""


def test_both_ternary_branches_are_discovered(tmp_path: Path) -> None:
    """Both the ``if`` and ``else`` branch keys of a ternary ``tr()`` argument
    are collected — not just whichever branch a naive first-literal
    resolver happens to see."""
    (tmp_path / "fixture_ternary_module.py").write_text(_FIXTURE_MODULE, encoding="utf-8")

    keys = scan_source_tree(tmp_path)

    assert "fixture.ternary.branch_true" in keys, (
        "the ternary's `if` branch key was not discovered — scan_source_tree regressed"
    )
    assert "fixture.ternary.branch_false" in keys, (
        "the ternary's `else` branch key was not discovered — this is the exact blind "
        "spot the ternary-argument fix in locales/_ast_scanner.py closes; a first-"
        "literal-only resolver passes for the `if` branch above while silently missing "
        "this one."
    )
