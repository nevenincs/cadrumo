"""Follow translated parameters through wrappers without collecting other arguments."""

import ast
from pathlib import Path

import pytest

from .._ast_key_wrappers import _extract_positional_translation_key_arguments, _translation_key_parameter_positions

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_wrappers_follow_a_key_in_a_later_parameter_to_explicit_locale_lookup() -> None:
    tree = ast.parse(
        "def authored(key, locale): return lookup_translation(key, locale=locale)\n"
        "def route(kind, key, locale): return authored(key, locale)\n"
        "def template(key, locale): return route('template', key, locale)\n"
        "rendered = template('docs.site.active', 'en')\n"
        "other = route('docs.site.not-a-key', 'docs.site.used', 'en')\n"
    )
    positions = _translation_key_parameter_positions([(Path("example.py"), tree)])

    assert positions["route"] == frozenset({1})
    assert _extract_positional_translation_key_arguments(tree, positions) == {"docs.site.active", "docs.site.used"}


def test_conflicting_wrapper_definitions_do_not_admit_a_position() -> None:
    first = ast.parse("def render(key, value): return lookup_translation(key, locale=value)\n")
    second = ast.parse("def render(key, value): return lookup_translation(value, locale=key)\n")
    positions = _translation_key_parameter_positions([(Path("first.py"), first), (Path("second.py"), second)])

    assert "render" not in positions
