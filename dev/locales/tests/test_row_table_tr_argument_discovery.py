"""A locale key reaching ``tr`` from a ROW TABLE must be discoverable.

The scanner already recognizes a dict registry (``{token: "some.key"}``) read
into a translator. A second table shape ships in this codebase and the dict
test cannot see it: a tuple of equal-width tuples where one COLUMN holds the
translation key and the siblings hold the framework's English source strings
and defaults, iterated as ``for prefix, key, default, _ in TABLE`` and reaching
``tr(key)``.

That invisibility had a cost. ``cli.help.missing_argument``,
``cli.help.missing_option`` and ``cli.help.missing_parameter`` are shipped in
all four catalogues and required there by
``entrypoints/cli/tests/test_framework_localisation_catalogue_coverage.py``,
yet the locale audit reported them as EXTRA keys no codebase reference
justifies -- so the parity and audit gates stayed red while the only two
resolutions available were both wrong: delete the keys and red the
framework-localisation gate, leaving a Spanish operator half an English
refusal, or keep them and red parity. Teaching the scanner the shape is the
third option, and the one that leaves both gates honest.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .._ast_scanner import scan_source_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FRAMEWORK_MODULE = (
    Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "entrypoints" / "cli" / "_framework_localisation.py"
)
_TABLE_ROUTED_KEYS = frozenset(
    {
        "cli.help.missing_argument",
        "cli.help.missing_option",
        "cli.help.missing_parameter",
    }
)

#: A row table read by ``tr``. The key column is the second; the siblings are
#: prose, which is the whole reason the dict shape's "every value is a key"
#: test cannot be applied here.
_ROUTED = '''
TABLE = (
    ("Missing argument", "cli.help.missing_argument", "Missing argument"),
    ("Missing option", "cli.help.missing_option", "Missing option"),
)


def render(rendered):
    for prefix, key, default in TABLE:
        if rendered.startswith(prefix):
            return tr(key, default=default)
    return rendered
'''

#: The SAME table, never read by a translator. Shape alone must not qualify it.
_UNROUTED = _ROUTED.replace("return tr(key, default=default)", "return default")

#: A table of the same shape whose columns are ordinary strings.
_PROSE = '''
PAIRS = (("alpha", "beta"), ("gamma", "delta"))


def render():
    for left, right in PAIRS:
        return tr(right)
'''


def _framework_tree() -> ast.Module:
    return ast.parse(_FRAMEWORK_MODULE.read_text(encoding="utf-8"))


def _keys_passed_as_tr_literals(tree: ast.Module) -> frozenset[str]:
    """The keys the scanner could already see WITHOUT understanding row tables."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"):
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            found.add(node.args[0].value)
    return frozenset(found)


def test_the_anchor_keys_are_still_reached_through_a_table_and_not_a_literal() -> None:
    """Guard the anchor: if these become literal ``tr("...")`` calls, this file proves nothing.

    Without this, converting the table to three literal calls would leave the
    discovery test below passing for a reason that has nothing to do with the
    shape it exists to cover.
    """
    literals = _keys_passed_as_tr_literals(_framework_tree())
    still_routed = _TABLE_ROUTED_KEYS - literals
    assert still_routed == _TABLE_ROUTED_KEYS, (
        "these keys are now passed to tr() as literals, so the row-table shape is no longer "
        f"exercised by this module and this test has gone vacuous: {sorted(_TABLE_ROUTED_KEYS & literals)}"
    )


def test_the_shipped_framework_keys_are_discoverable() -> None:
    source = _FRAMEWORK_MODULE.read_text(encoding="utf-8")
    discovered = scan_source_text(source, filename=str(_FRAMEWORK_MODULE))
    assert discovered >= _TABLE_ROUTED_KEYS, sorted(_TABLE_ROUTED_KEYS - discovered)


def test_a_row_table_read_by_the_translator_is_discovered() -> None:
    assert _TABLE_ROUTED_KEYS & scan_source_text(_ROUTED, filename="routed.py")


def test_a_row_table_never_read_by_the_translator_is_not_discovered() -> None:
    """Flow confirmation, not shape, decides -- otherwise any string table qualifies."""
    assert not (_TABLE_ROUTED_KEYS & scan_source_text(_UNROUTED, filename="unrouted.py"))


def test_a_prose_table_read_by_the_translator_yields_no_keys() -> None:
    """A column that is prose in any row is not a key column."""
    assert not scan_source_text(_PROSE, filename="prose.py")
