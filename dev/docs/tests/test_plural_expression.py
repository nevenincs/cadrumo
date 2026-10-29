"""The desktop documentation's plural-form evaluator against Sphinx's own.

Sphinx builds each language's plural-form function from the catalog's gettext
expression with ``new Function``, which the desktop window's script policy
refuses. ``docs/_static/cadrumo-plural-expression.js`` replaces that with an
evaluator that builds no code from the string. These gates run the real script
in Chromium against every expression Sphinx ships and compare it, count by
count, with the function Sphinx itself would have built.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_SCRIPT = REPO_ROOT / "docs" / "_static" / "cadrumo-plural-expression.js"
#: The counts both functions answer for: the small ones every rule distinguishes,
#: the teens and hundreds the Slavic rules turn on, a million for the "millions"
#: form, and fractions the rules that test ``n % 1`` separate.
_COUNTS = [*range(0, 130), 200, 1001, 1011, 10000, 100000, 999999, 1000000, 2000000, 0.5, 1.5, 2.5]

_STUB = """const Documentation = { TRANSLATIONS: {}, PLURAL_EXPR: null, LOCALE: null };"""


def _shipped_expressions() -> dict[str, str]:
    """Return the plural expression of every language interface-string file Sphinx installs."""
    import sphinx

    expressions: dict[str, str] = {}
    for path in sorted((Path(sphinx.__file__).parent / "locale").glob("*/LC_MESSAGES/sphinx.js")):
        match = re.search(r'"plural_expr"\s*:\s*("(?:[^"\\]|\\.)*")', path.read_text(encoding="utf-8"))
        assert match is not None, f"{path} carries no plural expression"
        expressions[path.parts[-3]] = json.loads(match.group(1))
    return expressions


@pytest.fixture(scope="module")
def evaluator() -> Iterator[Any]:
    """A page holding Sphinx's ``Documentation`` stand-in with the real script loaded over it."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content("<!doctype html><html><body></body></html>")
            page.add_script_tag(content=_STUB)
            page.add_script_tag(path=str(_SCRIPT))
            yield page
        finally:
            browser.close()


def test_the_shipped_expressions_are_the_set_this_gate_compares() -> None:
    """The comparison is not vacuous: Sphinx ships many languages, among them the three Cadrumo builds."""
    expressions = _shipped_expressions()
    assert len(expressions) > 30
    assert {"es", "ca", "hu"} <= expressions.keys()


def test_every_shipped_expression_selects_the_form_sphinx_would(evaluator: Any) -> None:
    """For every language and count, the evaluator and ``new Function`` choose the same form."""
    differences = evaluator.evaluate(
        """([expressions, counts]) => {
          const found = [];
          for (const [language, expression] of Object.entries(expressions)) {
            Documentation.addTranslations({ messages: {}, plural_expr: expression, locale: language });
            const reference = new Function("n", `return (${expression})`);
            for (const n of counts) {
              const expected = Number(reference(n));
              const actual = Documentation.PLURAL_EXPR(n);
              if (expected !== actual) found.push([language, expression, n, expected, actual]);
            }
          }
          return found;
        }""",
        [_shipped_expressions(), _COUNTS],
    )
    assert differences == []


def test_the_catalog_is_still_merged_and_the_locale_recorded(evaluator: Any) -> None:
    """Replacing the function keeps the rest of what ``addTranslations`` does."""
    state = evaluator.evaluate(
        """() => {
          Documentation.TRANSLATIONS = {};
          Documentation.addTranslations({ messages: { Search: "Buscar" }, plural_expr: "(n != 1)", locale: "ca" });
          const form = Documentation.PLURAL_EXPR;
          return [Documentation.TRANSLATIONS, Documentation.LOCALE, form(1), form(3)];
        }"""
    )
    assert state == [{"Search": "Buscar"}, "ca", 0, 1]


@pytest.mark.parametrize(
    "expression",
    ["alert(1)", "n.constructor", "(n != 1", "n ?", "n n", "n; n", "`${n}`", "this", "n ** 2", ""],
)
def test_an_expression_outside_the_gettext_language_is_refused_not_evaluated(evaluator: Any, expression: str) -> None:
    """Anything the evaluator cannot read as arithmetic is an error that names it, never run."""
    refusal = evaluator.evaluate(
        """(expression) => {
          try {
            Documentation.addTranslations({ messages: {}, plural_expr: expression, locale: "xx" });
            return null;
          } catch (error) {
            return error.message;
          }
        }""",
        expression,
    )
    assert refusal == f"unsupported plural expression: {expression}"
