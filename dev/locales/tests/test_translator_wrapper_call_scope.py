"""A translator wrapper is reached only by the call form its definition admits."""

import ast
from pathlib import Path

import pytest

from .._ast_key_calls import _extract_error_constructor_keys
from .._ast_key_wrappers import _translation_wrapper_names

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFINITIONS = (
    "def field(key, /, *, id):\n    return tr(key)\nclass Copy:\n    def say(self, key):\n        return tr(key)\n"
)
_CALLS = (
    "field('tui.example.label', id='x')\n"
    "schema.field('provenance.source')\n"
    "Copy().say('tui.example.said')\n"
    "say('tui.example.bare_method_name')\n"
    "i18n.tr('tui.example.attribute_translator')\n"
)


def _keys() -> set[str]:
    definitions = ast.parse(_DEFINITIONS)
    calls = ast.parse(_CALLS)
    wrappers = _translation_wrapper_names([(Path("copy.py"), definitions), (Path("screen.py"), calls)])
    return _extract_error_constructor_keys(calls, wrappers)


def test_a_function_wrapper_is_reached_by_its_bare_name_only() -> None:
    keys = _keys()

    assert "tui.example.label" in keys
    assert "provenance.source" not in keys


def test_a_method_wrapper_is_reached_through_an_attribute_only() -> None:
    keys = _keys()

    assert "tui.example.said" in keys
    assert "tui.example.bare_method_name" not in keys


def test_the_translator_itself_is_still_reached_through_an_attribute() -> None:
    assert "tui.example.attribute_translator" in _keys()
