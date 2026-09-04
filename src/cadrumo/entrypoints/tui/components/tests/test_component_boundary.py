"""Boundary proofs for the canonical TUI presentation-component package."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .....core.presentation import FormField
from ..dialogs import TextEditScreen
from ..errors import ErrorPanel
from ..logs import BoundedLogPanel
from ..status import PinnedStatusBar
from ..theme import install_cadrumo_themes
from ..widgets import ContentDataTable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_presentation_symbols_have_one_direct_canonical_home() -> None:
    """Consumers import reusable presentation mechanics from their defining module."""
    assert tuple(
        symbol.__module__
        for symbol in (TextEditScreen, ErrorPanel, FormField, BoundedLogPanel, PinnedStatusBar, ContentDataTable)
    ) == (
        "cadrumo.entrypoints.tui.components.dialogs",
        "cadrumo.entrypoints.tui.components.errors",
        "cadrumo.core.presentation",
        "cadrumo.entrypoints.tui.components.logs",
        "cadrumo.entrypoints.tui.components.status",
        "cadrumo.entrypoints.tui.components.widgets",
    )
    assert install_cadrumo_themes.__module__ == "cadrumo.entrypoints.tui.components.theme"


def test_no_query_passes_a_subscripted_generic_as_its_expected_type() -> None:
    """`query_one(sel, Foo[str])` type-checks and then raises at mount.

    Textual `isinstance`-checks that second argument, and Python refuses an
    instance check against a subscripted generic:
    `TypeError: Subscripted generics cannot be used with class and instance
    checks`. The failure is at MOUNT, so the screen dies rather than
    misbehaving, and it is invisible to both the type checker and any test
    that does not actually mount the screen.

    This is not hypothetical. A refactor that read as a tidy-up -- replacing
    `cast("ContentDataTable[str]", self.query_one(sel, ContentDataTable))`
    with `self.query_one(sel, ContentDataTable[str])` -- landed at two sites in
    the Ledger entries screen and took eight tests down with it. The correct
    form keeps the bare class at runtime and puts the element type in a cast.

    Scanned statically across the whole TUI package because the defect is a
    SHAPE, not a behaviour: catching it needs one pass over the source, while
    catching it dynamically needs every screen mounted in every state.
    """
    package = Path(__file__).resolve().parent.parent.parent
    offenders: list[str] = []
    for source in package.rglob("*.py"):
        if "tests" in source.parts:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"query", "query_one", "get_child_by_type"}:
                continue
            for argument in node.args[1:]:
                if isinstance(argument, ast.Subscript):
                    offenders.append(
                        f"{source.relative_to(package)}:{node.lineno} {node.func.attr}(..., {ast.unparse(argument)})"
                    )

    assert not offenders, (
        "these calls pass a subscripted generic where Textual will isinstance-check it, "
        "which raises TypeError at mount; use the bare class and cast the result:\n" + "\n".join(offenders)
    )
