"""Export refusals carry catalogue words, so the operator never reads developer English.

Each refusal below is raised by the real export code and rendered through the
error renderer in every supported locale. A second check reads the source of
every filing module whose refusals were moved to catalogue words and renders each
key it names with a context that fills every placeholder.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ....core.errors.error_codes import resolve_error_message
from ....core.i18n.render import tr
from ....core.modelo import Modelo
from ....domain.filing.errors import FilingExportError
from .. import export_xml_dictionary_values as values_module
from ..export import _validate_envelope_identity_option, _validate_envelope_prefix_options
from ..export_xml_dictionary import _bounded_repeated_rows, read_xml_dictionary_root_identity
from ..export_xml_dictionary_values import format_xml_dictionary_value
from ..m190_context_validation import _M190_NEGATIVE_SIGN, _require_m190_reintegro_context
from ..m193_context_validation import _require_devengo_year_before_filing

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_FILING_DIR = Path(__file__).resolve().parents[1]
_WORDED_MODULES = (
    "export.py",
    "export_envelope.py",
    "export_xml_dictionary.py",
    "export_xml_dictionary_modelo100.py",
    "export_xml_dictionary_values.py",
    "m190_context_validation.py",
    "m193_context_validation.py",
    "m280_context_validation.py",
    "m347_declarado_row_scope.py",
    "projection.py",
    "record_field_renderer.py",
    "record_renderer.py",
)
_KEY_PREFIX = "application.filing.export.errors."
_PLACEHOLDER = re.compile(r"%\{(\w+)\}")


def _assert_catalogue_words(error: BaseException, key: str) -> None:
    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert words, (locale, key)
        assert words != key, (locale, key)
        assert "%{" not in words, (locale, words)
        assert not words.startswith(("application.", "errors.")), (locale, words)


def _raised(call: object) -> FilingExportError:
    assert callable(call)
    with pytest.raises(FilingExportError) as caught:
        call()
    return caught.value


def test_envelope_identity_refusal_is_catalogue_words() -> None:
    error = _raised(lambda: _validate_envelope_identity_option(True, None))
    assert error.translated_message == _KEY_PREFIX + "product_identity_required"
    _assert_catalogue_words(error, "product_identity_required")


def test_envelope_dictionary_values_refusal_is_catalogue_words() -> None:
    error = _raised(
        lambda: _validate_envelope_prefix_options(
            modelo=_a_modelo(),
            requires_product_identity=False,
            product_software_identity=None,
            dictionary_values={"x": "y"},
            prior_domiciliation_election=None,
        )
    )
    _assert_catalogue_words(error, "dictionary_values_not_admitted")


def _a_modelo() -> Modelo:
    return Modelo("111")


def test_unreadable_xml_payload_refusal_is_catalogue_words() -> None:
    error = _raised(lambda: read_xml_dictionary_root_identity(b"<unclosed"))
    assert error.translated_message == _KEY_PREFIX + "xml_payload_unreadable"
    _assert_catalogue_words(error, "xml_payload_unreadable")


def test_wrong_xml_root_refusal_names_both_roots() -> None:
    error = _raised(lambda: read_xml_dictionary_root_identity(b"<NotTheDictionaryRoot/>"))
    for locale in _LOCALES:
        assert "NotTheDictionaryRoot" in resolve_error_message(error, locale=locale)
    _assert_catalogue_words(error, "xml_payload_root_differs")


def test_too_many_rows_refusal_states_the_limit() -> None:
    rows = {1: {}, 2: {}}
    error = _raised(lambda: _bounded_repeated_rows("Filas", rows, {}, limit=1, activity_grained=False))
    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert "Filas" in words
        assert "2" in words
    _assert_catalogue_words(error, "xml_rows_exceed_schema")


def test_text_date_refusal_is_catalogue_words() -> None:
    error = _raised(lambda: format_xml_dictionary_value(values_module._DATE_DICTIONARY_TYPE, "1980-01-02"))
    _assert_catalogue_words(error, "xml_date_form_refused")


def test_ambiguous_amount_refusal_is_catalogue_words() -> None:
    error = _raised(lambda: format_xml_dictionary_value("P012", "1.000"))
    _assert_catalogue_words(error, "xml_amount_unreadable")


def test_m190_zero_reintegro_refusal_is_catalogue_words() -> None:
    error = _raised(
        lambda: _require_m190_reintegro_context(
            marker=str(_M190_NEGATIVE_SIGN),
            magnitude="000",
            retention="0",
            filing_year="0010",
            devengo_year="0001",
        )
    )
    _assert_catalogue_words(error, "m190_reintegro_magnitude_zero")


def test_m193_devengo_year_refusal_names_the_modelo() -> None:
    error = _raised(lambda: _require_devengo_year_before_filing("0007", "0007"))
    for locale in _LOCALES:
        assert "193" in resolve_error_message(error, locale=locale)
    _assert_catalogue_words(error, "devengo_year_not_earlier")


def _string_constants(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(_KEY_PREFIX)
    }


@pytest.mark.parametrize("module_name", _WORDED_MODULES)
def test_every_key_a_worded_module_names_renders_words_in_all_locales(module_name: str) -> None:
    keys = _string_constants(ast.parse((_FILING_DIR / module_name).read_text(encoding="utf-8")))
    assert keys, module_name
    for key in sorted(keys):
        english = tr(key, locale="en")
        assert english != key, key
        fill = {name: "x" for name in _PLACEHOLDER.findall(english)}
        for locale in _LOCALES:
            words = tr(key, locale=locale, **fill)
            assert words and words != key, (locale, key)
            assert "%{" not in words, (locale, key, words)
