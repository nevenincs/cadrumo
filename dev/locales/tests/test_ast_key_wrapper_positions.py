"""Follow translated parameters through wrappers without collecting other arguments."""

import ast
from pathlib import Path

import pytest

from .._ast_key_wrappers import _extract_positional_translation_key_arguments, _translation_key_parameter_positions
from .._ast_scanner import scan_source_tree

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


@pytest.mark.parametrize("parameter", ["message_key", "value"])
def test_later_key_parameters_confirm_scalar_and_dict_constants(tmp_path: Path, parameter: str) -> None:
    (tmp_path / "renderer.py").write_text(
        "def wording(value): return lookup_translation(value, locale='en')\n"
        f"def catalogue_words(error_code, {parameter}, context=None): return wording({parameter})\n",
        encoding="utf-8",
    )
    (tmp_path / "refusal_words.py").write_text(
        "from typing import Final\n"
        "from renderer import catalogue_words\n"
        "_VALIDATION_KEY: Final = 'application.example.served.validation'\n"
        "_DUPLICATE_KEY: Final = 'application.example.served.duplicate'\n"
        "_DISPOSAL_KEYS: Final[dict[str, str]] = {\n"
        "    'route.year': 'application.example.served.year',\n"
        "    'route.regime': 'application.example.served.regime',\n"
        "}\n"
        "def refusal(reason, error_code):\n"
        "    catalogue_words(error_code, _VALIDATION_KEY)\n"
        "    catalogue_words(error_code, _DUPLICATE_KEY, {'identifier': 'route.identity'})\n"
        "    catalogue_words(error_code, _DISPOSAL_KEYS[reason])\n",
        encoding="utf-8",
    )

    assert scan_source_tree(tmp_path) == {
        "application.example.served.validation",
        "application.example.served.duplicate",
        "application.example.served.year",
        "application.example.served.regime",
    }


def test_later_key_parameters_reject_other_arguments_and_untranslated_constants(tmp_path: Path) -> None:
    (tmp_path / "renderer.py").write_text(
        "def catalogue_words(error_code, value, context=None): return lookup_translation(value, locale='en')\n",
        encoding="utf-8",
    )
    (tmp_path / "refusal_words.py").write_text(
        "from typing import Final\n"
        "from renderer import catalogue_words\n"
        "_FIRST_KEY: Final = 'application.example.wrong.first'\n"
        "_THIRD_KEY: Final = 'application.example.wrong.third'\n"
        "_UNUSED_KEY: Final = 'application.example.unused'\n"
        "_ROUTES: Final = {'route.first': 'application.example.wrong.mapping'}\n"
        "_NOT_COPY: Final = {'route.other': 'application.example.untranslated'}\n"
        "_COPY: Final = {'route.copy': 'application.example.used'}\n"
        "def refusal(reason):\n"
        "    catalogue_words(_FIRST_KEY, 'application.example.literal', _THIRD_KEY)\n"
        "    catalogue_words(_ROUTES[reason], 'application.example.literal')\n"
        "    record(_NOT_COPY[reason])\n"
        "    key = _COPY.get(reason)\n"
        "    catalogue_words('application.example.wrong.code', key, {'x': 'application.example.wrong.context'})\n",
        encoding="utf-8",
    )

    assert scan_source_tree(tmp_path) == {"application.example.literal", "application.example.used"}
