"""Every catalogue key the Typer-framework localisation cites must be shipped.

The framework localisation layer re-keys Typer's own English strings ("Missing
argument", "Invalid value", the help panel headings) onto catalogue entries so a
Spanish operator does not meet half a refusal in English. Some of those keys
reach :func:`tr` through a lookup TABLE rather than as a literal first argument,
and the locale scaffold's extractor only sees ``tr("literal")`` — so a
table-routed key is invisible to the locale catalogue scaffolder, can never be
scaffolded, and silently falls back to its English default in all four locales.

That is exactly how ``cli.help.missing_argument``, ``cli.help.missing_option``
and ``cli.help.missing_parameter`` came to be absent from every catalogue while
the drift check reported none missing.

The gate therefore derives its denominator from the module's OWN source rather
than from the scaffold's view, and proves the indirection is inside that
denominator before checking resolution.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODULE_PATH = Path(__file__).resolve().parents[1] / "_framework_localisation.py"
_LOCALES = (OutputLanguage.ES, OutputLanguage.EN, OutputLanguage.CA, OutputLanguage.HU)

# A dotted catalogue key under the framework-localisation namespace. Narrow to
# that namespace so ordinary prose and Typer's English source strings (which are
# also literals in this module) cannot be mistaken for keys.
_CATALOGUE_KEY_PATTERN = re.compile(r"^cli\.help\.[a-z0-9_.]+$")


def _module_tree() -> ast.Module:
    return ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))


def _cited_catalogue_keys(tree: ast.Module) -> frozenset[str]:
    """Every catalogue key literal in the module, however it reaches ``tr``."""
    return frozenset(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _CATALOGUE_KEY_PATTERN.match(node.value)
    )


def _directly_translated_keys(tree: ast.Module) -> frozenset[str]:
    """Only the keys passed as ``tr("literal", ...)``, which the scaffold can see."""
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tr"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            keys.add(first.value)
    return frozenset(keys)


def test_framework_localisation_cites_keys_the_scaffold_cannot_see() -> None:
    """The indirection this gate exists for must still be present.

    Without this, the module could drift to citing every key directly, the
    scaffold would then cover them all, and a green result below would say
    nothing about the table-routed class that actually failed.
    """
    tree = _module_tree()
    cited = _cited_catalogue_keys(tree)
    direct = _directly_translated_keys(tree)

    assert cited, "no framework-localisation catalogue keys were found; the extractor is blind"
    indirect = cited - direct
    assert indirect, (
        "every framework-localisation key now reaches tr() as a literal. If that is deliberate, this "
        "gate's premise is gone and it should be retired rather than left passing vacuously."
    )


def test_every_framework_localisation_key_ships_a_real_value_in_every_locale() -> None:
    """A cited key must resolve to real text in all four shipped catalogues.

    Resolution goes through the production catalogue reader, so a key present
    only as a scaffold placeholder (value equal to its own key) fails here just
    as an absent one does: both hand the operator an untranslated string.
    """
    failures: list[str] = []
    for key in sorted(_cited_catalogue_keys(_module_tree())):
        for locale in _LOCALES:
            try:
                value = lookup_translation(key, locale=locale.value)
            except Exception as exc:
                failures.append(f"{key} [{locale.value}]: unresolvable ({type(exc).__name__}: {exc})")
                continue
            if not isinstance(value, str) or not value.strip():
                failures.append(f"{key} [{locale.value}]: empty value")
            elif value.strip() == key:
                failures.append(f"{key} [{locale.value}]: self-referencing placeholder, not a translation")

    assert not failures, (
        "framework-localisation keys are cited by production code but not shipped as real catalogue "
        "values, so Typer's English wording reaches the operator:\n" + "\n".join(failures)
    )


def test_the_missing_prefix_keys_are_genuinely_translated_across_locales() -> None:
    """Anti-tautology guard: the four catalogues must not echo one English string.

    A parity check alone passes when every locale carries the same English text,
    which is the state this work corrected.
    """
    for key in ("cli.help.missing_argument", "cli.help.missing_option", "cli.help.missing_parameter"):
        rendered = {locale.value: lookup_translation(key, locale=locale.value) for locale in _LOCALES}
        assert len(set(rendered.values())) == len(_LOCALES), f"{key} is not distinctly translated: {rendered}"
